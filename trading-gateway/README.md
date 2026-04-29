# MiniQMT Trading Gateway

Windows-side HTTP gateway for MiniQMT/xtquant.

```bash
pip install -r requirements.txt
python server.py --port 8800 --miniqmt-path "D:\\国金证券QMT交易端\\userdata_mini"
```

The Mac backend defaults to `dry_run`. Live trading only happens when `trading.mode`
is set to `live` and the gateway is reachable.
