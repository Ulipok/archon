import sys
import archon.exchange.exchanges as exc
import archon.broker as broker
import archon.arch as arch
import archon.markets as m
import archon.feeds.cryptocompare as cryptocompare
import json
import requests
import time
import datetime

abroker = broker.Broker()
arch.setClientsFromFile(abroker)
a = arch.Arch()

client = abroker.get_client(exc.BINANCE)

ae = [exc.KUCOIN, exc.BITTREX, exc.CRYPTOPIA, exc.HITBTC, exc.BINANCE]
a.set_active_exchanges(ae)

ms = a.fetch_global_markets()
print (len(ms))

ms2 = list(filter(lambda x: x['denom'] == 'BTC', ms))
print (len(ms2))

for x in ms2:
    print (x)


"""
a.sync_markets_all()
ms = a.get_markets()

print ("markets per exchange")
exs = list(set([x['exchange'] for x in ms]))
for e in exs:
    z = list(filter(lambda t: t['exchange']==e, ms))
    print (e,len(z))

ms = sorted(ms, key=lambda k: k['volume']) 

print ("simple screen sorted by volume\npair last")
for m in ms[:100]:
        if m['denom']!="BTC": continue
        print (m['pair'],m['last'])
"""

