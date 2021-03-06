import archon.broker as broker
import archon.arch as arch
import archon.exchange.exchanges as exc
import archon.markets as m
import archon.model.models as models
from archon.util import *

import time
import datetime
import math

abroker = broker.Broker()
arch.setClientsFromFile(abroker)
client = abroker.get_client(exc.BINANCE)

market = models.get_market("RVN","BTC",exc.BINANCE)
txdata = abroker.trade_history(market,exc.BINANCE)

def total(data):
    x = [x['quantity'] for x in data]
    return sum(x)

def vwap(data):
    vwap = 0
    t = total(data)
    for b in data:    
        f = b['quantity']/t
        p = b['price']
        vwap += p*f
    return vwap    

buys = list()
sells = list()
for x in txdata:
    if x['txtype']=='BUY':
        buys.append(x)
    else:
        sells.append(x)


tb = total(buys)
ts = total(sells)
open_amount = (tb-ts)
print (tb,ts)

buy_vwap = vwap(buys)
sell_vwap = vwap(sells)

total_cost = buy_vwap*tb
total_value = sell_vwap*ts

pnl = total_value - total_cost
roi = pnl/total_cost
print (pnl,roi)