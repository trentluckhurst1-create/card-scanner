from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from card_scanner.active_price_comparison import build_active_price_comparisons
from card_scanner.cli import opportunity_store_source
from card_scanner.dashboard_export import market_listing_to_dashboard_record
from card_scanner.exact_discovery import discover_exact_inventory
from card_scanner.market_catalogue import MarketListingObservation
from card_scanner.models import Listing
from card_scanner.opportunity_scanner import SPORTS, MultiStoreSource, NamedStoreSource
from card_scanner.retrying_source import RetryingStoreSource
from card_scanner.sources.boop import BoopSource
from card_scanner.sources.clfox import CLFoxSource
from card_scanner.sources.eastside import EastsideSource
from card_scanner.sources.local_card_shop import LocalCardShopSource
from card_scanner.sources.the_hobby import TheHobbySource

ACTIVE_MARKET_SCHEMA_VERSION = 1

def _now() -> str: return datetime.now(timezone.utc).isoformat()
def _dedupe(listings: Iterable[Listing]) -> list[Listing]:
    output=[]; seen=set()
    for listing in listings:
        key=(str(listing.source),str(listing.external_id))
        if key not in seen: seen.add(key); output.append(listing)
    return output

def _source_token(value: object)->str: return re.sub(r"[^a-z0-9]+","",str(value or "").casefold())
def _text_token(value: object)->str: return " ".join(str(value or "").casefold().split())

def _shared_player_year_targets(listings: Iterable[Listing], *, max_targets:int):
    grouped=defaultdict(set); labels={}
    for listing in listings:
        identity=listing.identity
        if identity is None or not identity.player or not identity.year: continue
        sport=str(listing.sport).upper(); player_key=_text_token(identity.player); year=str(identity.year).strip()
        if not player_key or not year: continue
        key=(sport,player_key,year); grouped[key].add(_source_token(listing.source)); labels[key]=str(identity.player).strip()
    candidates=[(sport,labels[(sport,p,y)],y,sources) for (sport,p,y),sources in grouped.items() if len(sources)>=2]
    candidates.sort(key=lambda row:(-len(row[3]),row[0],row[1].casefold(),row[2])); return candidates[:max(0,int(max_targets))]

def expand_shared_player_inventory(source:MultiStoreSource,listings:Iterable[Listing],*,max_targets:int=20,results_per_store:int=50):
    base_rows=_dedupe(listings); targets=_shared_player_year_targets(base_rows,max_targets=max_targets)
    stores_by_token={_source_token(getattr(s.source,"name",None) or s.name):s for s in source.stores}
    expanded=list(base_rows); errors=[]; query_count=0
    for sport,player,year,participant_tokens in targets:
        for source_token in sorted(participant_tokens):
            store=stores_by_token.get(source_token)
            if store is None: continue
            query_count+=1
            try: found=store.source.search(sport=sport,query=player,limit=max(1,int(results_per_store)))
            except Exception as exc: errors.append(f"{sport}: {store.name}: deep overlap search: {type(exc).__name__}: {exc}"); continue
            target_player=_text_token(player)
            for row in found:
                identity=row.identity
                if identity is not None and _text_token(identity.player)==target_player and str(identity.year or "").strip()==year: expanded.append(row)
    expanded=_dedupe(expanded)
    return expanded,{"deep_overlap_targets":len(targets),"deep_overlap_queries":query_count,"deep_overlap_added_cards":max(0,len(expanded)-len(base_rows)),"deep_overlap_errors":len(errors)},errors

def build_active_market_payload(listings:Iterable[Listing],*,generated_at:str|None=None,store_errors:Iterable[str]=(),stores_considered:int=4,stores_searched:int=4,discovery_metrics:dict[str,int]|None=None)->dict:
    rows=_dedupe(listings); errors=tuple(store_errors); cards=[market_listing_to_dashboard_record(MarketListingObservation(listing=row)) for row in rows]; comparisons=build_active_price_comparisons(cards)
    by_source={}; by_sport={}
    for card in cards:
        source=str(card.get("source") or "UNKNOWN"); sport=str(card.get("sport") or "UNKNOWN"); by_source[source]=by_source.get(source,0)+1; by_sport[sport]=by_sport.get(sport,0)+1
    metrics={"active_cards":len(cards),"stores_considered":stores_considered,"stores_searched":stores_searched,"store_error_count":len(errors),"comparison_groups":comparisons["comparison_group_count"],"exact_matches":comparisons["exact_match_count"],"same_product_variants":comparisons["same_product_variant_count"],"player_year_markets":comparisons["player_year_market_count"]}; metrics.update(discovery_metrics or {})
    return {"schema_version":ACTIVE_MARKET_SCHEMA_VERSION,"generated_at":generated_at or _now(),"feed_type":"ACTIVE_MARKET_COMPARISON_ONLY","pricing_basis":"ACTIVE_ASKS_ONLY_NOT_FAIR_VALUE","governance":{"contains_sold_evidence":False,"contains_fair_value":False,"can_create_buy":False,"persistent_history_claimed":False},"metrics":metrics,"by_source":dict(sorted(by_source.items())),"by_sport":dict(sorted(by_sport.items())),"store_errors":list(errors),"market_cards":cards,"active_price_comparisons":comparisons}

def _retry_store(store:NamedStoreSource)->NamedStoreSource: return NamedStoreSource(name=store.name,source=RetryingStoreSource(store.source,attempts=3,base_delay_seconds=0.4))
def cloud_active_store_source()->MultiStoreSource:
    source,_=opportunity_store_source("all")
    if not isinstance(source,MultiStoreSource): raise RuntimeError("Expected all-store MultiStoreSource")
    raw_stores=[*source.stores,NamedStoreSource(name="The Hobby",source=TheHobbySource()),NamedStoreSource(name="Eastside Collectables",source=EastsideSource()),NamedStoreSource(name="Boop Collectables",source=BoopSource()),NamedStoreSource(name="CLFox Collectables",source=CLFoxSource()),NamedStoreSource(name="Local Card Shop",source=LocalCardShopSource())]
    return MultiStoreSource([_retry_store(store) for store in raw_stores])

def collect_active_market(*,limit_per_store_per_sport:int,source:MultiStoreSource|None=None):
    source=source or cloud_active_store_source(); listings=[]; errors=[]; stores_searched_total=0; stores_considered_total=0; searched_store_names=set()
    for sport in SPORTS:
        result=source.collect(sport=sport,query="",limit=limit_per_store_per_sport); listings.extend(result.listings); errors.extend(f"{sport}: {m}" for m in result.store_errors); stores_considered_total=max(stores_considered_total,result.stores_considered)
        for listing in result.listings: searched_store_names.add(str(listing.source))
        if result.stores_searched: stores_searched_total=max(stores_searched_total,result.stores_searched)
    return _dedupe(listings),stores_considered_total,max(stores_searched_total,len(searched_store_names)),errors

def main()->int:
    parser=argparse.ArgumentParser(description="Publish a secret-free active-store comparison feed."); parser.add_argument("--limit-per-store-per-sport",type=int,default=125); parser.add_argument("--deep-overlap-targets",type=int,default=20); parser.add_argument("--deep-results-per-store",type=int,default=50); parser.add_argument("--exact-discovery-targets",type=int,default=16); parser.add_argument("--exact-results-per-store",type=int,default=100); parser.add_argument("--output",default="docs/active_market.json"); args=parser.parse_args()
    cloud_source=cloud_active_store_source(); listings,stores_considered,stores_searched,errors=collect_active_market(limit_per_store_per_sport=max(1,args.limit_per_store_per_sport),source=cloud_source)
    listings,discovery_metrics,deep_errors=expand_shared_player_inventory(cloud_source,listings,max_targets=max(0,args.deep_overlap_targets),results_per_store=max(1,args.deep_results_per_store)); errors.extend(deep_errors)
    listings,exact_stats,exact_errors=discover_exact_inventory(cloud_source,listings,max_targets=max(0,args.exact_discovery_targets),results_per_store=max(1,args.exact_results_per_store)); errors.extend(exact_errors); discovery_metrics.update({"exact_discovery_targets":exact_stats.targets,"exact_discovery_queries":exact_stats.queries,"exact_discovery_added_cards":exact_stats.added_cards,"exact_discovery_matches":exact_stats.exact_matches_discovered,"exact_discovery_errors":exact_stats.errors})
    payload=build_active_market_payload(listings,store_errors=errors,stores_considered=stores_considered,stores_searched=stores_searched,discovery_metrics=discovery_metrics); output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); metrics=payload["metrics"]
    print("CARD_SCANNER_ACTIVE_MARKET_PUBLISH=PASS"); print(f"ACTIVE_CARDS={metrics['active_cards']}"); print(f"STORES_SEARCHED={metrics['stores_searched']}/{metrics['stores_considered']}"); print(f"STORE_ERRORS={metrics['store_error_count']}")
    for source_name,count in payload["by_source"].items(): print(f"ACTIVE_SOURCE_{source_name.upper().replace(' ','_')}={count}")
    for sport,count in payload["by_sport"].items(): print(f"ACTIVE_SPORT_{sport.upper()}={count}")
    for index,message in enumerate(payload["store_errors"],start=1): print(f"STORE_ERROR_{index}={message}")
    for key in ("deep_overlap_targets","deep_overlap_queries","deep_overlap_added_cards","deep_overlap_errors","exact_discovery_targets","exact_discovery_queries","exact_discovery_added_cards","exact_discovery_matches","exact_discovery_errors"): print(f"{key.upper()}={metrics.get(key,0)}")
    print(f"COMPARISON_GROUPS={metrics['comparison_groups']}"); print(f"EXACT_MATCHES={metrics['exact_matches']}"); print(f"SAME_PRODUCT_VARIANTS={metrics['same_product_variants']}"); print(f"PLAYER_YEAR_MARKETS={metrics['player_year_markets']}"); print("SOLD_EVIDENCE_INCLUDED=NO"); print("FAIR_VALUE_INCLUDED=NO"); print("PERSISTENT_HISTORY_CLAIMED=NO"); print(f"OUTPUT={output.as_posix()}"); return 0
if __name__=="__main__": raise SystemExit(main())
