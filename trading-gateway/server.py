from __future__ import annotations

import argparse
import random

from flask import Flask, jsonify, request

app = Flask(__name__)
_trader = None
_account = None
_config = {}


@app.route("/connect", methods=["POST"])
def connect():
    global _trader, _account, _config
    _config = request.json or {}
    try:
        from xtquant import xttrader  # type: ignore

        path = _config.get("miniqmt_path") or _config.get("path") or ""
        account_id = _config.get("stock_account", "")
        session_id = random.randint(100000, 999999)
        _trader = xttrader.XtQuantTrader(path, session_id)
        _trader.start()
        result = _trader.connect()
        if result != 0:
            return jsonify({"success": False, "message": f"connect failed: {result}"})
        _account = xttrader.StockAccount(account_id) if account_id else None
        if _account is not None:
            _trader.subscribe(_account)
        return jsonify({"success": True})
    except Exception as exc:
        return jsonify({"success": False, "message": str(exc)})


@app.route("/asset", methods=["GET"])
def asset():
    return jsonify({"total_asset": 0, "market_value": 0, "cash": 0, "frozen_cash": 0, "mode": "gateway"})


@app.route("/positions", methods=["GET"])
def positions():
    return jsonify({"positions": []})


@app.route("/orders", methods=["GET"])
def orders():
    return jsonify({"orders": []})


@app.route("/order", methods=["POST"])
def order():
    data = request.json or {}
    if _trader is None:
        return jsonify({"status": "rejected", "message": "gateway not connected"}), 503
    try:
        from xtquant import xtconstant  # type: ignore

        side = data.get("side")
        order_type = xtconstant.STOCK_BUY if side == "buy" else xtconstant.STOCK_SELL
        price_type = xtconstant.FIX_PRICE
        order_id = _trader.order_stock(
            account=_account,
            stock_code=f"{data['symbol']}.{_exchange(data['symbol'])}",
            order_type=order_type,
            order_volume=int(data["volume"]),
            price_type=price_type,
            price=float(data.get("price") or 0),
        )
        return jsonify({"entrust_no": str(order_id), "status": "submitted"})
    except Exception as exc:
        return jsonify({"status": "rejected", "message": str(exc)}), 500


@app.route("/cancel", methods=["POST"])
def cancel():
    return jsonify({"success": False, "message": "cancel not implemented in skeleton"})


def _exchange(symbol: str) -> str:
    return "SH" if str(symbol).startswith(("5", "6", "9")) else "SZ"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8800)
    parser.add_argument("--miniqmt-path", default="")
    args = parser.parse_args()
    _config["miniqmt_path"] = args.miniqmt_path
    app.run(host="0.0.0.0", port=args.port)
