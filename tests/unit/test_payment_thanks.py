from src.texts.payment_thanks import THANKS, payment_thanks


def test_thanks_are_short_varied_and_stable_for_recovered_receipts():
    assert len(set(THANKS)) >= 60
    assert len(THANKS) == len(set(THANKS))
    assert max(map(len, THANKS)) < 160
    assert payment_thanks('charge1') == payment_thanks('charge1')
    assert len({payment_thanks(f'charge{i}') for i in range(100)}) > 1
    assert payment_thanks() in THANKS
