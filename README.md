# binance_frame
相较于之前的布林线策略代码，现在能够动态获取binance交易所api所支持的交易对

之前使用的方法为静态获取json格式的数据，放入代码中

但会有更新的问题

bolling_quant.py负责交易连接ccxt以及交易所

如果想使用其他策略的话，只需要更改trade的代码，更改策略

也就是新制作一个策略，将其写入signal_bolling（）函数中，生成dataframe格式，将其return

但是要注意新策略的信号必须干净
