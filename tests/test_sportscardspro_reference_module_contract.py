import inspect

import card_scanner.sportscardspro_reference as ref


def test_reference_module_exposes_only_pure_lookup_building_functions():
    functions = {name for name, value in vars(ref).items() if inspect.isfunction(value) and value.__module__ == ref.__name__}
    assert functions == {"exact_research_terms", "search_url_for_exact_group"}
