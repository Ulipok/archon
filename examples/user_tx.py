import sys
import archon.broker as broker
import archon.arch as arch
import archon.exchange.exchanges as exc
import time
import datetime

from archon.util import *
from util import *
#from order_utils import *

import math

abroker = broker.Broker()
arch.setClientsFromFile(abroker)

def user_tx():
    #db.user_txs.find()   
    a = arch.Arch()
    ae = [exc.KUCOIN, exc.BITTREX, exc.CRYPTOPIA, exc.BINANCE]
    #ae = [exc.BITTREX] #, exc.BINANCE]
    a.set_active_exchanges(ae)

    txs = a.global_tradehistory()
    print (len(txs))
    for tx in txs[:]:        
        #print (tx)
        ts = tx['timestamp'][:19]
        timestamp_from = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S')        
        #tx["timestamp"] = timestamp_from
        m = tx['market']        
        tday = timestamp_from.day        
        #print (tx)
        if tday>20:
            r = tx['price']
            a = tx['quantity']
            ty = tx['txtype']
            #print (m,r,a,ty)
     
if __name__=='__main__':
    user_tx()