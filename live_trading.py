import os
import time
import schedule
import logging
import ccxt
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv
import json

from dfa_strategy import DFAStrategyLogic

# 加载环境变量
load_dotenv()

class DFALiveTrading:
    def __init__(self):
        self.setup_logging()
        self.setup_exchange()
        self.load_strategy_state()
        self.logger.info("🚀 DFA实盘交易系统初始化完成")
        
    def setup_logging(self):
        """设置日志系统"""
        # 确保logs目录存在
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/trading.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('DFA_Live')
        
    def setup_exchange(self):
        """设置币安连接 - 修复代理配置"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 代理配置
                proxy_config = None
                if os.getenv('USE_PROXY', 'false').lower() == 'true':
                    proxy_config = os.getenv('PROXY_URL', 'http://10.48.175.246:7897')
                    self.logger.info(f"🔌 使用代理: {proxy_config}")
                
                exchange_config = {
                    'apiKey': os.getenv('BINANCE_API_KEY', 'dry_run_test_key'),
                    'secret': os.getenv('BINANCE_API_SECRET', 'dry_run_test_secret'),
                    'sandbox': os.getenv('SANDBOX_MODE', 'false').lower() == 'true',
                    'enableRateLimit': True,
                    'timeout': 30000,
                    'options': {
                        'defaultType': 'spot',
                        'adjustForTimeDifference': True,
                    },
                }
                
                # 修复：为CCXT配置代理会话
                if proxy_config:
                    session = requests.Session()
                    session.proxies = {
                        'http': proxy_config,
                        'https': proxy_config,
                    }
                    exchange_config['session'] = session
                    self.logger.info("✅ 已配置代理会话")
                
                self.exchange = ccxt.binance(exchange_config)
            
                # 测试连接
                time_data = self.exchange.fetch_time()
                server_time = datetime.fromtimestamp(time_data / 1000).strftime('%Y-%m-%d %H:%M:%S')
                self.logger.info(f"✅ 币安连接成功（第{attempt+1}次尝试）")
                self.logger.info(f"⏰ 服务器时间: {server_time}")
                if proxy_config:
                    self.logger.info("🔌 通过代理连接")
                else:
                    self.logger.info("🌐 直接连接")
                return
            
            except Exception as e:
                self.logger.warning(f"⚠️ 第{attempt+1}次连接失败: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    self.logger.info(f"🔄 {wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    self.logger.error("❌ 所有连接尝试都失败")
                    raise

    def load_strategy_state(self):
        """加载多币种策略状态"""
        try:
            os.makedirs('data', exist_ok=True)
            
            state_file = 'data/multi_strategy_state.json'
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                from multi_asset_strategy import MultiAssetDFAStrategy
                self.strategy = MultiAssetDFAStrategy()
                self.strategy.from_dict(state)
                self.logger.info("✅ 多币种策略状态加载成功")
            else:
                from multi_asset_strategy import MultiAssetDFAStrategy
                self.strategy = MultiAssetDFAStrategy()
                self.logger.info("📝 初始化新多币种策略")
                
        except Exception as e:
            self.logger.error(f"❌ 加载策略状态失败: {e}")
            raise

    def save_strategy_state(self):
        """保存多币种策略状态"""
        try:
            with open('data/multi_strategy_state.json', 'w', encoding='utf-8') as f:
                json.dump(self.strategy.to_dict(), f, indent=2, ensure_ascii=False)
            self.logger.debug("💾 多币种策略状态已保存")
        except Exception as e:
            self.logger.error(f"❌ 保存策略状态失败: {e}")
    
    def get_current_price(self, symbol='SOL/USDT'):
        """获取当前价格"""
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            price = ticker['last']
            self.logger.info(f"💰 当前价格: ${price:.4f}")
            return price
        except Exception as e:
            self.logger.error(f"❌ 获取价格失败: {e}")
            return None
    
    def calculate_ma120(self, symbol='SOL/USDT'):
        """计算MA120指标"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, '1d', limit=120)
            
            if len(ohlcv) < 120:
                self.logger.warning(f"⚠️ 数据只有 {len(ohlcv)} 天")
                actual_period = len(ohlcv)
            else:
                actual_period = 120
                
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            ma_value = df['close'].mean()
            
            start_date = pd.to_datetime(df['timestamp'].iloc[0], unit='ms').strftime('%Y-%m-%d')
            end_date = pd.to_datetime(df['timestamp'].iloc[-1], unit='ms').strftime('%Y-%m-%d')
            
            self.logger.info(f"📊 MA120计算: {actual_period}天数据 ({start_date} 到 {end_date})")
            self.logger.info(f"📈 MA120数值: ${ma_value:.4f}")
            
            return ma_value
            
        except Exception as e:
            self.logger.error(f"❌ 计算MA120失败: {e}")
            return None
    
    def get_account_balance(self):
        """获取账户余额"""
        try:
            # Dry Run模式下返回模拟余额
            dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
            if dry_run:
                self.logger.info("💡 模拟账户余额: 1000.00 USDT")
                return 1000.0
            
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['total'].get('USDT', 0)
            free_balance = balance['free'].get('USDT', 0)
            
            self.logger.info(f"💳 账户总余额: {usdt_balance:.2f} USDT")
            self.logger.info(f"💳 可用余额: {free_balance:.2f} USDT")
            
            return free_balance
            
        except Exception as e:
            self.logger.error(f"❌ 获取余额失败: {e}")
            return None
    
    def execute_buy_order(self, symbol, amount, price):
        """执行买入订单"""
        try:
            dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
            
            if dry_run:
                self.logger.info(f"💡 模拟买入: {amount:.4f} {symbol} @ ${price:.4f}")
                self.logger.info(f"💡 模拟金额: ${amount * price:.2f}")
                return {'id': 'DRY_RUN_BUY', 'status': 'simulated'}
            else:
                self.logger.info(f"🚀 实际买入: {amount:.4f} {symbol}")
                order = self.exchange.create_market_buy_order(symbol, amount)
                self.logger.info(f"✅ 买入订单完成: {order['id']}")
                return order
                
        except Exception as e:
            self.logger.error(f"❌ 买入订单失败: {e}")
            return None
    
    def execute_sell_order(self, symbol, amount, price):
        """执行卖出订单"""
        try:
            dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
            
            if dry_run:
                self.logger.info(f"💡 模拟卖出: {amount:.4f} {symbol} @ ${price:.4f}")
                self.logger.info(f"💡 模拟金额: ${amount * price:.2f}")
                return {'id': 'DRY_RUN_SELL', 'status': 'simulated'}
            else:
                self.logger.info(f"🚀 实际卖出: {amount:.4f} {symbol}")
                order = self.exchange.create_market_sell_order(symbol, amount)
                self.logger.info(f"✅ 卖出订单完成: {order['id']}")
                return order
                
        except Exception as e:
            self.logger.error(f"❌ 卖出订单失败: {e}")
            return None
    
    def run_strategy_check(self):
        """执行多币种策略检查"""
        self.logger.info("=" * 60)
        self.logger.info("🔍 开始多币种策略检查")
        self.logger.info("=" * 60)
        
        current_date = datetime.now().date()
        current_prices = {}
        ma120_values = {}
        
        # 为每个币种获取市场数据
        for symbol in self.strategy.symbols:
            self.logger.info(f"\n📊 处理 {symbol}...")
            
            price = self.get_current_price(symbol)
            ma120 = self.calculate_ma120(symbol)
            
            if price is not None and ma120 is not None:
                current_prices[symbol] = price
                ma120_values[symbol] = ma120
                
                deviation = (price - ma120) / ma120 * 100
                self.logger.info(f"   当前价格: ${price:.4f}")
                self.logger.info(f"   MA120: ${ma120:.4f}")
                self.logger.info(f"   偏离度: {deviation:.1f}%")
            else:
                self.logger.error(f"❌ 获取 {symbol} 市场数据失败")
        
        # 执行每个币种的策略
        for symbol in self.strategy.symbols:
            if symbol not in current_prices:
                continue
                
            self.logger.info(f"\n🎯 执行 {symbol} 策略...")
            
            # 1. 检查减仓条件
            profit_result = self.strategy.execute_profit_taking(symbol, current_prices[symbol], current_date)
            if profit_result['action'] == 'sell':
                self.logger.info(f"   🎯 触发减仓条件!")
                self.logger.info(f"   卖出份额: {profit_result['size']:.4f}")
                
                order = self.execute_sell_order(
                    symbol, 
                    profit_result['size'], 
                    profit_result['price']
                )
                if order:
                    self.logger.info("   ✅ 减仓操作完成")
            else:
                self.logger.info(f"   ⏳ 减仓检查: {profit_result['reason']}")
            
            # 2. 检查投资条件
            if self.strategy.should_invest_today(current_date, symbol):
                available_cash = self.get_account_balance()
                investment_result = self.strategy.execute_investment(
                    symbol, current_prices[symbol], ma120_values[symbol], current_date, available_cash
                )
                
                if investment_result['action'] == 'buy':
                    self.logger.info(f"   🎯 触发投资条件!")
                    self.logger.info(f"   投资金额: ${investment_result['amount']:.2f}")
                    self.logger.info(f"   偏离程度: {investment_result['deviation']:.1f}%")
                    
                    order = self.execute_buy_order(
                        symbol,
                        investment_result['size'],
                        investment_result['price']
                    )
                    
                    if order:
                        state = self.strategy.symbol_states[symbol]
                        self.logger.info(f"   ✅ 第{state['investment_count']}期投资完成")
                else:
                    self.logger.info(f"   ⏳ 投资检查: {investment_result['reason']}")
            else:
                state = self.strategy.symbol_states[symbol]
                if state['last_investment_date']:
                    days_since_last = (current_date - state['last_investment_date']).days
                    days_remaining = self.strategy.investment_interval - days_since_last
                    self.logger.info(f"   📅 非投资日，还需等待 {days_remaining} 天")
        
        # 3. 打印投资组合状态
        self.print_multi_portfolio_status(current_prices)
        
        # 4. 保存状态
        self.save_strategy_state()
        
        self.logger.info("✅ 多币种策略检查完成\n")
    
    def print_multi_portfolio_status(self, current_prices):
        """打印多币种投资组合状态"""
        self.logger.info("\n📊 多币种投资组合详细报告")
        self.logger.info("=" * 50)
        
        total_assets = 0
        total_investment = 0
        
        for symbol in self.strategy.symbols:
            if symbol not in current_prices:
                continue
                
            status = self.strategy.get_portfolio_status(symbol, current_prices[symbol])
            
            self.logger.info(f"\n{symbol}:")
            self.logger.info(f"   定投期数: {status['investment_count']} 期")
            self.logger.info(f"   持仓数量: {status['total_shares']:.4f}")
            self.logger.info(f"   持仓成本: ${status['total_invested']:.2f}")
            self.logger.info(f"   当前价值: ${status['current_value']:.2f}")
            self.logger.info(f"   浮动收益: {status['current_return']:.1f}%")
            self.logger.info(f"   累计投资: ${status['total_investment']:.2f}")
            self.logger.info(f"   累计卖出: ${status['total_sell_amount']:.2f}")
            self.logger.info(f"   总资产: ${status['total_assets']:.2f}")
            self.logger.info(f"   总收益率: {status['total_return']:.1f}%")
            
            total_assets += status['total_assets']
            total_investment += status['total_investment']
        
        # 总投资组合汇总
        self.logger.info("\n💰 总投资组合汇总:")
        self.logger.info(f"   累计总投资: ${total_investment:.2f}")
        self.logger.info(f"   总资产价值: ${total_assets:.2f}")
        if total_investment > 0:
            total_return = ((total_assets - total_investment) / total_investment) * 100
            self.logger.info(f"   总投资收益率: {total_return:.1f}%")
        
    def health_check(self):
        """系统健康检查 - 支持真实API的Dry Run模式"""
        try:
            # 测试连接和API密钥有效性
            self.exchange.fetch_time()
            
            # 测试获取余额（验证API密钥权限）
            if os.getenv('DRY_RUN', 'true').lower() == 'true':
                self.logger.info("💡 Dry Run模式 - 测试API连接")
                # Dry Run模式下只测试连接，不进行完整余额检查
                price = self.get_current_price()
                if price:
                    self.logger.info("🟢 健康检查通过 - API连接正常")
                    return True
                else:
                    return False
            else:
                # 真实交易模式进行完整检查
                price = self.get_current_price()
                balance = self.get_account_balance()
                if price and balance is not None:
                    self.logger.info("🟢 健康检查通过")
                    return True
                else:
                    return False
                    
        except ccxt.AuthenticationError as e:
            self.logger.error(f"🔴 API密钥验证失败: {e}")
            return False
        except ccxt.PermissionDenied as e:
            self.logger.error(f"🔴 API权限不足: {e}")
            return False
        except Exception as e:
            self.logger.error(f"🔴 健康检查失败: {e}")
            return False
    def run(self):
        """主运行循环"""
        self.logger.info("🚀 DFA动态定投实盘系统启动 - 本地代理测试")
        
        dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
        if dry_run:
            self.logger.info("💡 当前模式: 模拟交易")
        else:
            self.logger.info("🚨 当前模式: 真实交易")
        
        if not self.health_check():
            self.logger.error("❌ 系统健康检查失败，无法启动")
            return
        
        check_time = os.getenv('CHECK_TIME', '20:00')
        schedule.every().day.at(check_time).do(self.run_strategy_check)
        
        self.logger.info(f"⏰ 定时任务: 每天 {check_time} 执行策略检查")
        self.logger.info("🔄 立即执行首次策略检查...")
        
        self.run_strategy_check()
        
        self.logger.info("⏳ 进入主循环，等待定时任务...")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)
                
        except KeyboardInterrupt:
            self.logger.info("⏹️ 用户手动停止系统")
        except Exception as e:
            self.logger.error(f"❌ 系统运行异常: {e}")
            self.logger.info("🔄 10秒后尝试重启...")
            time.sleep(10)
            self.run()
        finally:
            self.logger.info("🔚 系统停止运行")

if __name__ == '__main__':
    try:
        trader = DFALiveTrading()
        trader.run()
    except Exception as e:
        logging.error(f"❌ 系统启动失败: {e}")