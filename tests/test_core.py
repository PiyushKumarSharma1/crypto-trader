from nova.indicators import compute
from nova.models import Bar
from nova.risk import RiskManager
from nova.strategy import EnsembleStrategy
from nova.service import WalletConnection


def bars(n=120):
    return [Bar(i * 900_000, 100 + i, 102 + i, 99 + i, 101 + i, 1000 + i) for i in range(n)]


def test_signal_is_bounded():
    signal = EnsembleStrategy().evaluate(compute(bars()))
    assert signal.action in {"buy", "sell", "hold"}
    assert 0 <= signal.confidence <= 1


def test_risk_circuit_breaker():
    r = RiskManager(100, 10, 5).size("buy", 0.9, 100, 2, daily_loss=10)
    assert not r.allowed and r.notional_usd == 0


def test_risk_sets_exits():
    r = RiskManager(100, 10, 5).size("buy", 0.8, 100, 2)
    assert r.allowed and r.stop_price < 100 < r.take_profit_price


def test_wallet_metadata_validation():
    wallet = WalletConnection(address="0x" + "AB" * 20, chain_id="0x1")
    assert wallet.address == "0x" + "ab" * 20
    assert wallet.chain_id == "0x1"
