from unittest.mock import AsyncMock

import scripts.backfill_output_ports as script


async def test_main_runs_the_backfill_on_one_connection(monkeypatch, capsys):
    conn = AsyncMock()
    monkeypatch.setattr(script, "connect", AsyncMock(return_value=conn))
    run = AsyncMock(return_value=2)
    monkeypatch.setattr(script.BackfillOutputPortsUseCase, "execute", run)
    await script.main()
    run.assert_awaited_once()
    conn.close.assert_awaited_once()
    assert capsys.readouterr().out == "Backfilled output ports for 2 data products\n"


async def test_main_closes_the_connection_when_the_backfill_fails(monkeypatch):
    conn = AsyncMock()
    monkeypatch.setattr(script, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(
        script.BackfillOutputPortsUseCase,
        "execute",
        AsyncMock(side_effect=RuntimeError("db down")),
    )
    try:
        await script.main()
    except RuntimeError:
        pass
    conn.close.assert_awaited_once()
