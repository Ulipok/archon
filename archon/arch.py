
import toml
import archon.broker as broker
import archon.exchange.exchanges as exc
import archon.markets as markets
import time
from archon.model import models
from archon.util import *
from pymongo import MongoClient
import datetime
from archon.feeds import cryptocompare

logpath = './log'
log = setup_logger(logpath, 'archon_logger', 'archon')

def toml_file(fs):
    with open(fs, "r") as f:
        return f.read()

def parse_toml(filename):
    toml_string = toml_file(filename)
    parsed_toml = toml.loads(toml_string)
    return parsed_toml

def set_keys_exchange(abroker, e, keys):
    pubkey = keys["public_key"]
    secret = keys["secret"]
    abroker.set_api_keys(e,pubkey,secret)

"""
def setClientsFromFile(abroker,keys_filename="apikeys.toml"):
    apikeys = parse_toml(keys_filename)
    log.debug(apikeys)
        
    for k,v in apikeys.items():
        eid = exc.get_id(k)
        if eid >= 0:
            set_keys_exchange(abroker, eid, apikeys[k])
        else:
            print ("exchange not supported")

    try:
        gconf = parse_toml("conf.toml")
        mailconf = gconf["MAILGUN"]
        abroker.set_mail_config(gconf["apikey"], gconf["domain"],gconf["email_from"],gconf["email_to"])
    except:
        print ("conf.toml not found. skipping config")
"""
    
class Arch:
    """ 
    communitates with broker
    keeps datastructures in memory
    """

    def __init__(self):
        filename = "apikeys.toml"
        self.abroker = broker.Broker()
        #setClientsFromFile(self.abroker, filename)
        #in memory data
        self.balances = None
        self.openorders = list()
        self.submitted_orders = list()
        self.active_exchanges = None
        self.selected_exchange = None

        all_conf = parse_toml("conf.toml")
        #active_exchanges = all_conf["BROKER"]["active_exchanges"]
        #self.set_active_exchanges_name(active_exchanges)

        mongo_conf = all_conf["MONGO"]
        #mongoHost = mongo_conf['host']
        dbName = mongo_conf['db']        
        url = mongo_conf["url"]
        self.set_mongo(url, dbName)
        self.starttime = datetime.datetime.utcnow()
        
    def set_mongo(self, url, dbName):
        #self.mongoHost = mongoHost
        #self.mongoPort = mongoPort
        self.mongo_url = url
        log.info("using mongo " + str(url))
        self.mongoclient = MongoClient(self.mongo_url)
        log.info("db %s"%dbName)
        self.db = self.mongoclient[dbName]

    def get_db(self):
        return self.db

    def set_active_exchanges(self, exchanges):
        log.info("set active exchanges %s"%exchanges)
        self.active_exchanges = exchanges  

    def set_active_exchanges_name(self, exchanges_names):
        ne = list()
        for n in exchanges_names:
            eid = exc.get_id(n)
            ne.append(eid)
        self.active_exchanges = ne

    def set_keys_exchange_file(self,keys_filename="apikeys.toml"):
        print ("set keys ",self.active_exchanges)
        apikeys = parse_toml(keys_filename)
            
        for k,v in apikeys.items():
            eid = exc.get_id(k)
            if eid >= 0 and eid in self.active_exchanges:
                self.set_keys_exchange(eid, apikeys[k])
            else:
                print ("exchange not supported or not set")

    def set_keys_exchange(self, exchange, keys):
        pubkey = keys["public_key"]
        secret = keys["secret"]
        log.debug ("set keys %i %s"%(exchange,keys))
        self.db.apikeys.save({"exchange":exchange,"pubkey":pubkey,"secret":secret})
        self.abroker.set_api_keys(exchange, pubkey, secret)

    def get_apikeys_all(self):
        return list(self.db.apikeys.find())
    
    def sync_orders(self):
        self.openorders = self.global_openorders()

    def get_by_id(self, oid):
        x = list(filter(lambda x: x['oid'] == oid, self.openorders))
        return x[0]


    # --- facade data ---    

    def global_openorders(self):
        oo = list()
        for e in self.active_exchanges:
            z = self.abroker.open_orders(e)
            n = exc.NAMES[e]
            print (n)
            if len(z) > 0:
                for x in z:
                    x['exchange'] = n
                    oo.append(x)
            
        log.debug("all open orders " + str(oo))
        return oo  

    def all_balance(self):        
        bl = list()
        for e in self.active_exchanges:
            log.debug("get balance ",e)
            z = self.abroker.balance_all(e)
            log.debug(z,e)
            n = exc.NAMES[e]
            for x in z:
                x['exchange'] = n
                bl.append(x)
        log.info("balance all %s"%(str(bl)))
        return bl

    def global_balances(self):
        bl = list()
        log.info("active exchanges %s"%(self.active_exchanges))
        for e in self.active_exchanges:
            n = exc.NAMES[e]
            b = self.abroker.balance_all(exchange=e)
            if b == None: print ("could not fetch balances from %s"%n)
            for x in b:
                x['exchange'] = n
                s = x['symbol']
                t = float(x['amount'])
                bl.append(x)
        return bl

    def global_balances_usd(self):
        bl = list()
        for e in self.active_exchanges:
            n = exc.NAMES[e]
            b = self.abroker.balance_all(exchange=e)
            if b == None: print ("could not fetch balances from %s"%n)
            for x in b:
                x['exchange'] = n
                s = x['symbol']
                t = float(x['amount'])
                if t > 0:
                    usd_price = cryptocompare.get_usd(s)    
                    x['USDprice'] = usd_price        
                    x['USDvalue'] = round(t*usd_price,2)
                    
                    if x['USDvalue'] > 1:
                        bl.append(x)
        return bl

    def global_tradehistory(self):
        txlist = list()
        for e in self.active_exchanges:
            n = exc.NAMES[e]
            tx = self.abroker.get_tradehistory_all(exchange=e)
            for x in tx:
                txlist.append(x)
        return txlist

        
        

    def submit_order(self, order, exchange=None):
        if exchange is None: exchange=self.selected_exchange
        #TODO check balance before submit
        market,ttype,order_price,qty = order
        self.submitted_orders.append(order)
        self.abroker.submit_order(order, exchange)

    def cancel_order(self, oid):                
        order = self.get_by_id(oid)
        #oid, otype=None,exchange=None,symbol=None):
        oid, otype,exchange, market = order['oid'],order['otype'],order['exchange'],order['market']
        exchange = exc.get_id(exchange)
        self.abroker.cancel_id(oid, otype, market, exchange)

    def cancel_all(self, exchange=None):
        #log.info("cancel all")
        if exchange is None: exchange=self.selected_exchange
        self.sync_orders()
        for o in self.openorders:
            log.info("cancel " + str(o))
            self.cancel_order(o['oid'])
        
    def fetch_global_markets(self):
        allmarkets = list()
        for e in self.active_exchanges:
            n = exc.NAMES[e]
            log.info("fetch %s"%n)
            m = self.abroker.get_market_summaries(e)
            for x in m:
                x['exchange'] = n
            allmarkets += m
        return allmarkets

    def aggregate_book(self, books):
        allbids = list()
        allasks = list()
        ts = None
        for z in books:
            b = z['bids']
            allbids += b
            a = z['asks']
            allasks += a
            ts = z['timestamp']
        allbids = sorted(allbids, key=lambda k: k['price'])
        allbids.reverse()
        allasks = sorted(allasks, key=lambda k: k['price'])
        return [allbids,allasks,ts]


    def global_orderbook(self, market):
        #self.db.orderbooks.drop()
        log.info("global orderbook for %s"%market)
        allbids = list()
        allasks = list()
        ts = None
        for e in self.active_exchanges:            
            n = exc.NAMES[e]
            x = self.db.orderbooks.find({'market':market,'exchange':n})            
            for z in x:
                b = z['bids']
                for xb in b: xb['exchange'] = n
                allbids += b

                a = z['asks']
                for xb in a: xb['exchange'] = n
                allasks += a
                ts = z['timestamp']

        allbids = sorted(allbids, key=lambda k: k['price'])
        allbids.reverse()        
        allasks = sorted(allasks, key=lambda k: k['price'])
        return [allbids,allasks,ts]

    def global_txhistory(self, market):
        tx_all = list()
        for e in self.active_exchanges:            
            n = exc.NAMES[exchange]
            txs = a.abroker.market_history(market,e)
            for tx in txs:
                tx["exchange"] = n
                tx_all.append(tx)
        return tx_all

    def filter_markets(self, m):
        f = lambda x: markets.is_btc(x['pair'])
        m = list(filter(f, m))
        return m

    def get_markets(self,exchange=None,denom=None):
        f = {}
        if exchange:
            f = {'exchange':exchange}
        if denom:
            f['denom'] = denom
        m = list(self.db.markets.find(f))
        #else:
        #    m = list(self.db.markets.find())
        return m

    def get_candle(self, market):
        log.debug("get candle " + market)
        result = self.db.candles.find_one({'market': market})        
        return result

    def sync_orderbook(self, market, exchange):
        smarket = models.conv_markets_to(market, exchange)  
        #print ("sync",market," ",exchange)   
        #TODO check if symbol is supported by exchange   
        try:
            n = exc.NAMES[exchange]
            [bids,asks] = self.abroker.get_orderbook(smarket,exchange)
            dt = datetime.datetime.utcnow()
            x = {'market': market, 'exchange': n, 'bids':bids,'asks':asks,'timestamp':dt}
            
            self.db.orderbooks.remove({'market':market,'exchange':n})
            self.db.orderbooks.insert(x)
            self.db.orderbooks_history.insert(x)
        except:
            log.info("sync book failed. symbol not supported")

    def sync_orderbook_all(self, market):   
        self.db.orderbooks.drop()     
        for e in self.active_exchanges:            
            self.sync_orderbook(market, e) 

    def sync_balances(self):
        balances = self.global_balances()
        print ("insert ",balances)
        self.db.balances.drop()
        dt = datetime.datetime.utcnow()
        self.db.balances.insert({'balance_items':balances,'t':dt})
        self.db.balances_history.insert(balances)

    def latest_balances(self):
        b = self.db.balances.find_one()
        return b


    def get_global_orderbook(self, market):
        books = list()
        for e in self.active_exchanges:
            log.info("global orderbook %i %s"%(e,market))
            #smarket = models.conv_markets_to(market, e)  
            try:
                n = exc.NAMES[e]
                [bids,asks] = self.abroker.get_orderbook(market,e)
                dt = datetime.datetime.utcnow()
                n = exc.NAMES[e]
                for xb in bids: xb['exchange'] = n
                for xa in asks: xa['exchange'] = n

                x = {'market': market, 'exchange': n, 'bids':bids,'asks':asks,'timestamp':dt}
                books.append(x)
            except Exception as err:
                log.error("error global orderbook %i %s %s"%(e,market,err))
        [bids,asks,ts] = self.aggregate_book(books)
        return [bids,asks,ts]

    def sync_tx(self, market, exchange):
        try:            
            smarket = models.conv_markets_to(market, exchange)  
            txs = self.abroker.market_history(smarket,exchange)
            n = exc.NAMES[exchange]
            smarket = models.conv_markets_to(market, exchange)
            dt = datetime.datetime.utcnow()
            x = {'market': market, 'exchange': n, 'tx':txs,'timestamp':dt}
            self.db.txs.remove({'market':market,'exchange':n})
            self.db.txs.insert(x)     
            self.db.txs_history.insert(x)
        except:
            print ("symbol not supported")

    def sync_tx_all(self, market):              
        for e in self.active_exchanges:
            self.db.txs.remove({'market':market,'exchange':e})
            self.sync_tx(market, e)   

    def sync_markets_all(self):
        self.db.markets.drop()
        ms = self.fetch_global_markets()
        dt = datetime.datetime.utcnow()        
        nm = list()
        for x in ms:
            try:
                dts = dt.strftime('%H:%M:%S')
                x['timestamp'] = dts
                n,d = x['pair'].split('_')
                x['nom'] = n
                x['denom'] = d   
                self.db.markets.insert(x)
                self.db.markets_history.insert(x)
            except:
                pass


    def sync_candle_daily(self, market, exchange):
        log.debug("get candles %s %s "%(market, str(exchange)))
        candles = self.abroker.get_candles_daily(market, exchange)
        n = exc.NAMES[exchange]
        n,d = market.split('_')
        self.db.candles.insert({"exchange":n,"market":market,"nom":n,"denom":d,"candles":candles,"interval": "1d"})

    def sync_candles_all(self, market):
        for e in self.active_exchanges:            
            self.sync_candle_daily(market, e)   

    def sync_candle_daily_all(self):
        ms = self.fetch_global_markets()
        log.info(len(ms))

        #cndl = self.abroker.get_candles_daily(market,exc.BINANCE)

        for x in ms[:]:
            market = x['pair']
            log.info("sync %s"%market)
            try:
                self.sync_candle_daily(market,exc.BINANCE)
            except:
                pass


        #for e in self.active_exchanges:            
        #    #self.sync_candle_daily(market, e)   




    def transaction_queue(self,exchange):
        now = datetime.datetime.utcnow()
        #delta = now - self.starttime
        txs = self.abroker.get_tradehistory_all(exchange)
        for tx in txs[:]:
            ts = tx['timestamp'][:19]
            dt = datetime.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%S')        
            if dt > self.starttime:
                print ("new tx")
            
"""
def tx_history_converted(nom, denom, exchange):
    if exchange == exc.CRYPTOPIA:   
        market = markets.get_market(nom,denom,exchange) 
        txs = abroker.market_history(market,exchange)
        txs.reverse()
        new_txs_list = list() 
        print (len(txs))   
        for txitem in txs[:]:
            #print ("convert "+ str(txitem))
            txd = model.convert_tx(txitem, exc.CRYPTOPIA, market)
            new_txs_list.append(txd)
        return new_txs_list
    elif exchange == exc.BITTREX:  
        market = markets.get_market(nom,denom,exc.BITTREX)
        txs = abroker.market_history(market,exc.BITTREX)
        txs.reverse()
        #log.info("txs " + str(txs[:3]))    
        new_txs_list = list()            
        for txitem in txs[:]:
            txd = model.convert_tx(txitem, exc.BITTREX, market)
            new_txs_list.append(txd)
        return new_txs_list

    elif exchange == exc.KUCOIN:  
        market = markets.get_market(nom,denom,exc.KUCOIN)
        txs = abroker.market_history(market,exc.KUCOIN)
        new_txs_list = list()
        for txitem in txs:
            txd = model.convert_tx(txitem, exchange, market)
            new_txs_list.append(txd)
        return new_txs_list
"""            
        


