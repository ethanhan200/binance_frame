#! /usr/bin/python
# -*- codeing = utf-8 -*-
# @Time : 2021-09-09 14:25
# @Author : yjh
# @File : Trader.py
# @Software : PyCharm

import ccxt
import datetime
import time
import pandas as pd
from email.mime.text import MIMEText
from smtplib import SMTP

def next_run_time(time_interval,ahead_time=1):
    if time_interval.endswith('m'):
        nowtime = datetime.datetime.now()
        interval = int(time_interval.strip('m'))
        target_min = ((int(nowtime.minute / interval)) + 1 ) *interval
        if target_min < 60:
            target_time = nowtime.replace(minute=target_min,second=0,microsecond=0)
        else:
            if nowtime.hour == 23:
                target_time = nowtime.replace(hour=0,minute=0,second=0,microsecond=0)
                target_time += datetime.timedelta(days=1)
            else:
                target_time = nowtime.replace(hour=nowtime.hour+1,minute=0,second=0,microsecond=0)

        if (target_time - datetime.datetime.now()).seconds < ahead_time+1:
            print("距离target_time不足",ahead_time,"秒下次再运行")
            target_time += datetime.timedelta(interval)
        print("下次运行时间",target_time)
        return target_time
    else:
        exit("please use 'm' to calculate time")

def get_binance_candle_data(exchange,symbol,time_interval):
    # 抓取数据
    content = exchange.fetch_ohlcv(symbol=symbol,timeframe=time_interval,limit=100)
    df = pd.DataFrame(content, dtype=float)
    df.rename(columns={
        0: 'MTS', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume'
    }, inplace=True)  # 重命名
    df['candle_begin_time'] = pd.to_datetime(df['MTS'], unit='ms')
    df['candle_begin_time_GMT8'] = df['candle_begin_time'] + datetime.timedelta(hours=8)  # 换成东八区时间
    df = df[['candle_begin_time_GMT8', 'open', 'high', 'low', 'close', 'volume']]
    return df


def get_binance_contract_candadle(exchange,pair,type,interval,limit):
    content = exchange.fapipublic_get_continuousklines(
        {
            'pair':pair,'contractType':type,'interval':interval,'limit':limit
        } # limit 是int型
    )
    df = pd.DataFrame(content, dtype=float)
    df.rename(columns={
        0: 'MTS', 1: 'open', 2: 'high', 3: 'low', 4: 'close', 5: 'volume'
    }, inplace=True)  # 重命名
    df['candle_begin_time'] = pd.to_datetime(df['MTS'], unit='ms')
    df['candle_begin_time_GMT8'] = df['candle_begin_time'] + datetime.timedelta(hours=8)  # GMT是格林威治标准时间
    df = df[['candle_begin_time_GMT8', 'open', 'high', 'low', 'close', 'volume']]
    return df
"""
合约类型:
PERPETUAL 永续合约
CURRENT_MONTH 当月交割合约
NEXT_MONTH 次月交割合约
CURRENT_QUARTER 当季交割合约
NEXT_QUARTER 次季交割合约
"""


def signal_bolling(df,para):
    n = para[0] # 移动平均线的天数
    m = para[1] # 系数

    # 中轨
    df['median'] = df['close'].rolling(n, min_periods=1).mean()
    # 上下轨
    df['std'] = df['close'].rolling(n, min_periods=1).std(ddof=0)  # ddof=0表示标准差
    df['upper'] = df['median'] + m * df['std']
    df['lower'] = df['median'] - m * df['std']
    # 获得做多信号
    condition1 = df['close'] > df['upper']
    condition2 = df['close'].shift(1) <= df['upper'].shift(1)
    df.loc[condition1 & condition2, 'signal_long'] = 1  # 将做多的信号设置为1
    # 做多平仓信号
    condition1 = df['close'] < df['median']
    condition2 = df['close'].shift(1) >= df['median'].shift(1)
    df.loc[condition1 & condition2, 'signal_long'] = 0  # 将做多平仓信号设置为0
    # 做空信号
    condition1 = df['close'] < df['lower']
    condition2 = df['close'].shift(1) >= df['lower'].shift(1)
    df.loc[condition1 & condition2, 'signal_short'] = -1  # 将做空的信号设置为-1
    # 做空平仓信号
    condition1 = df['close'] > df['median']
    condition2 = df['close'].shift(1) <= df['median'].shift(1)
    df.loc[condition1 & condition2, 'signal_short'] = 0  # 将做空平仓信号设置为0
    # 合并多空信号,去除重负信号 ,不可能存在同时开多开空的信号
    df['signal'] = df[['signal_long', 'signal_short']].sum(axis=1, skipna=True,min_count=1)
    temp = df[df['signal'].notnull()][['signal']]  # 去掉空值的行,只留下有信号的
    temp = temp[temp['signal'] != temp['signal'].shift(1)]
    df['signal'] = temp['signal']
    df.drop(['median', 'upper', 'lower', 'std', 'signal_long', 'signal_short'], axis=1, inplace=True)
    return df

# 获取合约仓位
def get_perpetualContract_position(exchange,symbol):
    Contract_dic = {} #创建字典
    binance_positions = exchange.fapiprivatev2_get_account()['positions']
    i = len(binance_positions)
    for j in range(i):
        Contract_dic.update({str(binance_positions[j]['symbol']): j})
    num = Contract_dic[symbol]
    positionAmt = float(exchange.fapiprivatev2_get_account()['positions'][num]['positionAmt']) # 有正负
    return positionAmt

def get_contractAccount_balance(exchange,base_coin):
    dic={}  #需要运行fapiprivate_get_account函数去看字典里面的顺序 创建一个字典

    assetdic = exchange.fapiprivatev2_get_account()['assets']
    i = len(assetdic)
    for j in range(i):
        dic.update({str(assetdic[j]['asset']): j})
    num = dic[base_coin]
    asset =  float(exchange.fapiprivatev2_get_account()['assets'][num]['walletBalance'])
    return asset

# 下单函数
def place_order(exchange,pair,side,Order_type,price,quantity):
    for i in range(5):
        try:
            # 限价单
            if Order_type == 'LIMIT':
                if side == 'BUY':
                    order_info = exchange.fapiprivate_post_order({
                        'symbol': pair,'side': 'BUY',  'type': 'LIMIT','price': price,
                        'quantity': quantity,  'timeInForce': 'GTC',
                        # DAY（日内）GTC（取消前有效）OPG（第二天开盘提交）IOC（立刻执行或取消）FOK（全数执行或立即取消）DTC（日内直到取消）
                                        }
                                    )
                elif side == 'SELL':
                    order_info = exchange.fapiprivate_post_order({
                        'symbol': pair, 'side': 'SELL', 'type': 'LIMIT', 'price': price,
                        'quantity': quantity,'timeInForce': 'GTC',})
            # 市价单
            elif Order_type == 'MARKET':
                if side == 'BUY':
                    order_info = exchange.fapiprivate_post_order({
                        'symbol': pair, 'side': 'BUY', 'type': 'MARKET',
                        'quantity': quantity, 'timeInForce': 'GTC',})
                elif side == 'SELL':
                    order_info = exchange.fapiprivate_post_order({
                        'symbol': pair, 'side': 'BUY', 'type': 'MARKET',
                        'quantity': quantity, 'timeInForce': 'GTC', })
            else:
                pass
            print("下单成功",Order_type,side,pair,price,quantity)
            print("下单信息",order_info,"\n")
            return order_info
        except Exception as e:
            print("下单错误,1秒后重试",e)
            time.sleep(1)
    print("程序错误超过5次,退出")
    exit()

# 获取交易深度价格(买一价卖一价)
def get_price(exchange,side,pair):
    if side == 'SELL':
        price = float(exchange.fapipublic_get_depth({'symbol': pair, 'limit': 5})['bids'][0][0])
    elif side == 'BUY':
        price = float(exchange.fapipublic_get_depth({'symbol': pair, 'limit': 5})['asks'][0][0])
    return price