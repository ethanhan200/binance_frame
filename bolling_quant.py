#! /usr/bin/python
# -*- codeing = utf-8 -*-
# @Time : 2021-09-09 14:06
# @Author : yjh
# @File : bolling_quant.py
# @Software : PyCharm
import ccxt
import datetime
import time
import s_mail
from Trader import *
import pandas as pd
pd.set_option('display.width', 5000)
pd.set_option("max_colwidth",1000)
pd.set_option('display.max_columns',None)
pd.set_option('display.max_rows',None)



# ==参数设置
time_interval = '15m'
# 我的api
exchange = ccxt.binance(
    {
        "apiKey": "NQi7XRnkA1aGvdzRAI6WNWOtCuinH5ziRgqutoDLfA2zbAeOCV7UMCEKVeWDHj9B",
        "secret": "SZUOqUCFbfNDOCNrgi0DIdG5E3Fnqp12np8toxmhgjPSN2uRFCOeZHJ1fMYhUQiv"
    }
)

# 老弟的api
# exchange = ccxt.binance(
#     {
#         "apiKey": "sXc7X46SQ5i5y60U8jm2Km9AFSn7t2t03Ad57aWENE4JevKGXXpUyCxZQOUBJUbb",
#         "secret": "a9sIVUpPPOKUTyl7soOLC1eXrk0ELvtIWgz3ZujRsEcGtlaF0sYUGdzladfnIb6L"
#     }
# )

# symbol和pair最好一致
symbol = 'ETH/USDT'
pair = 'ETHUSDT' # 合约的交易对(ccxt隐式中用)
contractType = 'PERPETUAL'
base_coin = symbol.split('/')[-1]
trade_coin = symbol.split('/')[0]
buy_amount = 0# 以交易币种计算
lever = 2


"""
合约类型:
PERPETUAL 永续合约
CURRENT_MONTH 当月交割合约
NEXT_MONTH 次月交割合约
CURRENT_QUARTER 当季交割合约
NEXT_QUARTER 次季交割合约
"""

para = [91,2]  # 布林策略参数

# == 主函数
def main():

    while True:
        # 邮件内容
        # email_message = ''

        # # 从服务器上获取账户数据(现货)
        # balance = exchange.fetch_balance()['total']
        # base_coin_amount = float(balance[base_coin])
        # trade_coin_amount = float(balance[trade_coin])
        # print("当前资产\n",base_coin,base_coin_amount,trade_coin,trade_coin_amount)

################================================================================##################

        # 获取合约账户(U本位)
        base_coin_amount = get_contractAccount_balance(exchange,base_coin)
        trade_coin_amount =get_perpetualContract_position(exchange,pair) # 这个函数会取出负值说明是空仓
        print("当前资产\n", base_coin, base_coin_amount, trade_coin, trade_coin_amount)

        # email_message += str("当前资产:\n"+ base_coin+ str(base_coin_amount)+ trade_coin+ str(trade_coin_amount)+"\n")
################===============================================================###################
        # sleep到运行时间
        run_time = next_run_time(time_interval)
        # sleep 直到靠近下次运行时间
        time.sleep(max(0,(run_time-datetime.datetime.now()).seconds))
        while True:
            if run_time > datetime.datetime.now():
                continue
            else:
                break


        # # 获取最新数据(现货)
        # while True:
        #     df = get_binance_candle_data(exchange,symbol,time_interval)
        #     _temp = df[df['candle_begin_time_GMT8'] == (run_time - datetime.timedelta(minutes=int(time_interval.strip('m'))))]
        #     if _temp.empty:
        #         print("数据不包含最新数据,重新获取")
        #         continue
        #     else:
        #         break


        # 获取最新u本位永续合约数据
        while True:
            df = get_binance_contract_candadle(exchange,pair,contractType,interval=time_interval,limit=1000)
            _temp = df[df['candle_begin_time_GMT8'] == (run_time - datetime.timedelta(minutes=int(time_interval.strip('m'))))]
            if _temp.empty:
                print("数据不包含最新数据,重新获取")
                continue
            else:
                break

        # ==产生交易信号
        df = df[df['candle_begin_time_GMT8'] < pd.to_datetime(run_time)]
        df = signal_bolling(df,para=para)
        signal = df.iloc[-1]['signal']
        print("交易信号",signal)

        # email_message += ("交易信号"+str(signal)+'\n')
        # signal = 1
        # 越线信号(一根K线同时上穿或下穿两个轨道)
        df2 = df[df['signal'].notnull()][['signal']]
        if df2.iloc[-1]['signal']+df2.iloc[-2]['signal']==0:
            signal2 = True
        else:
            signal2 = False
        # print(df)
        #==== 识别信号下单
        if signal2 :
            if trade_coin_amount <0:
                price = get_price(exchange, 'BUY', pair)
                price *= 1.01
                price = round(price,2)
                _2trade = abs(trade_coin_amount) * 2
                orders_info = place_order(exchange, pair, 'BUY', 'LIMIT', price, quantity=(_2trade))
                print(orders_info)
                # email_message += str(orders_info)+"\n 平仓并做多,价格为:"+str(price)
                # 多两倍数量的多单平仓加做多
            elif trade_coin_amount > 0:
                price = get_price(exchange, 'SELL', pair)
                price *= 0.99
                price = round(price,2)
                _2trade = trade_coin_amount *2
                orders_info = place_order(exchange, pair, 'SELL', 'LIMIT', price, quantity=(_2trade))
                print(orders_info)
                # email_message += str(orders_info)+"\n 平仓并做空,价格为:"+str(price)
        else:
            # 空单平仓
            if signal == 0 and trade_coin_amount < 0:
                price = get_price(exchange,'BUY',pair)
                price *= 1.01
                price = round(price,2)
                orders_info = place_order(exchange,pair,'BUY','LIMIT',price,quantity=abs(trade_coin_amount))
                print(orders_info)
                # email_message += str(orders_info)+"\n 空单平仓,价格为:"+str(price)
            # 多单平仓
            if signal == 0 and trade_coin_amount > 0:
                price = get_price(exchange,'SELL',pair)
                price *= 0.99
                price = round(price,2)
                orders_info = place_order(exchange,pair,'SELL','LIMIT',price,quantity=trade_coin_amount)
                print(orders_info)
                # email_message += str(orders_info)+"\n 多单平仓,价格为:"+str(price)
            # 开多仓
            if signal == 1 and trade_coin_amount == 0:
                price = get_price(exchange, 'BUY', pair)
                price *= 0.1
                price = round(price,2)
                buy_amount = round(base_coin_amount * lever / price)
                orders_info = place_order(exchange, pair, 'BUY', 'LIMIT', price, quantity=buy_amount)
                print(orders_info)
                # email_message += str(orders_info)+"\n 做多,价格为:"+str(price)
            # 开空仓
            if signal == -1 and trade_coin_amount == 0:
                price = get_price(exchange, 'SELL', pair)
                price *= 0.99
                price = round(price,2)
                buy_amount = round(base_coin_amount * lever / price)
                orders_info = place_order(exchange, pair, 'SELL', 'LIMIT', price, quantity=buy_amount)
                print(orders_info)
                # email_message += str(orders_info)+"\n 做空,价格为:"+str(price)
        print("\n")
        # email_message += "\n"
        # s_mail.send_mail(email_message)
if __name__ == '__main__':
    main()