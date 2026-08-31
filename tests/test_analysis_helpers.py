import numpy as np

from catl_quant.analysis import _map_price_shock_to_pbt


def test_pass_through_reduces_positive_cost_shock_downside() -> None:
    shock = np.array([0.10])
    no_pass = _map_price_shock_to_pbt(202_723.479, 0.5, shock, 0.0)[0]
    high_pass = _map_price_shock_to_pbt(202_723.479, 0.5, shock, 0.9)[0]
    assert no_pass < high_pass < 0
    assert np.isclose(high_pass, no_pass * 0.1)
