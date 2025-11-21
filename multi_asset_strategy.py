import json
from datetime import datetime
import os

class MultiAssetDFAStrategy:
    def __init__(self):
        self.symbols = os.getenv('SYMBOLS', 'ETH/USDT,SOL/USDT,SUI/USDT').split(',')
        self.base_cash = {
            'ETH/USDT': float(os.getenv('BASE_CASH_ETH', 28)),
            'SOL/USDT': float(os.getenv('BASE_CASH_SOL', 28)), 
            'SUI/USDT': float(os.getenv('BASE_CASH_SUI', 14))
        }
        self.investment_interval = int(os.getenv('INVESTMENT_INTERVAL', 14))
        self.target_return = float(os.getenv('TARGET_RETURN', 75))
        self.sell_ratio = 0.5
        self.profit_taking_cooldown = 30
        
        # 为每个币种初始化状态
        self.symbol_states = {}
        for symbol in self.symbols:
            self.symbol_states[symbol] = {
                'investment_count': 0,
                'last_investment_date': None,
                'last_profit_taking_date': None,
                'total_invested': 0.0,
                'total_shares': 0.0,
                'total_sell_amount': 0.0,
                'investment_history': [],
                'profit_history': []
            }
    
    def get_investment_multiplier(self, deviation):
        """投资倍数计算"""
        if deviation <= -20: return 1.6
        elif deviation <= -10: return 1.4
        elif deviation <= 0: return 1.2
        elif deviation <= 5: return 1.0
        elif deviation <= 15: return 0.5
        elif deviation <= 25: return 0.2
        else: return 0.0
    
    def calculate_deviation(self, current_price, ma120_value):
        """计算价格偏离度"""
        if ma120_value == 0:
            return 0
        return (current_price - ma120_value) / ma120_value * 100
    
    def should_invest_today(self, current_date, symbol):
        """检查是否应该投资"""
        state = self.symbol_states[symbol]
        if state['last_investment_date'] is None:
            return True
        days_since_last = (current_date - state['last_investment_date']).days
        return days_since_last >= self.investment_interval
    
    def should_take_profit(self, current_date, current_return, symbol):
        """检查是否应该止盈"""
        state = self.symbol_states[symbol]
        if current_return < self.target_return:
            return False
        if state['last_profit_taking_date'] is not None:
            days_since_last = (current_date - state['last_profit_taking_date']).days
            if days_since_last < self.profit_taking_cooldown:
                return False
        return True
    
    def execute_investment(self, symbol, current_price, ma120_value, current_date, available_cash=None):
        """执行投资"""
        state = self.symbol_states[symbol]
        base_cash = self.base_cash[symbol]
        
        deviation = self.calculate_deviation(current_price, ma120_value)
        multiplier = self.get_investment_multiplier(deviation)
        investment_amount = base_cash * multiplier
        
        # 应用单次投资上限
        max_single_order = float(os.getenv('MAX_SINGLE_ORDER', 100))
        if investment_amount > max_single_order:
            investment_amount = max_single_order
        
        if available_cash is not None and investment_amount > available_cash:
            investment_amount = available_cash
        
        if investment_amount <= 0:
            return {'action': 'skip', 'reason': f'偏离度 {deviation:.1f}%，暂停投资'}
        
        size = round(investment_amount / current_price, 4)
        if size <= 0:
            return {'action': 'skip', 'reason': '计算出的购买数量为0'}
        
        actual_invested = size * current_price
        state['total_invested'] += actual_invested
        state['total_shares'] += size
        state['investment_count'] += 1
        state['last_investment_date'] = current_date
        
        investment_info = {
            'date': current_date.isoformat(),  # 直接保存为字符串
            'price': current_price,
            'ma120': ma120_value,
            'deviation': deviation,
            'multiplier': multiplier,
            'amount': actual_invested,
            'shares': size
        }
        state['investment_history'].append(investment_info)
        
        return {
            'action': 'buy',
            'symbol': symbol,
            'size': size,
            'amount': actual_invested,
            'price': current_price,
            'deviation': deviation,
            'multiplier': multiplier
        }
    
    def execute_profit_taking(self, symbol, current_price, current_date):
        """执行止盈"""
        state = self.symbol_states[symbol]
        
        if state['total_shares'] <= 0:
            return {'action': 'skip', 'reason': '暂无持仓'}
        
        current_value = state['total_shares'] * current_price
        if state['total_invested'] > 0:
            current_return = (current_value - state['total_invested']) / state['total_invested'] * 100
        else:
            current_return = 0
        
        if not self.should_take_profit(current_date, current_return, symbol):
            return {'action': 'skip', 'reason': f'收益率{current_return:.1f}%未达标'}
        
        sell_shares = round(state['total_shares'] * self.sell_ratio, 4)
        if sell_shares <= 0:
            return {'action': 'skip', 'reason': '计算出的卖出数量为0'}
        
        sell_amount = sell_shares * current_price
        cost_of_sold = (sell_shares / state['total_shares']) * state['total_invested']
        profit = sell_amount - cost_of_sold
        
        state['total_shares'] -= sell_shares
        state['total_invested'] -= cost_of_sold
        state['total_sell_amount'] += sell_amount
        state['last_profit_taking_date'] = current_date
        
        profit_info = {
            'date': current_date.isoformat(),  # 直接保存为字符串
            'price': current_price,
            'return_percent': current_return,
            'shares_sold': sell_shares,
            'amount_received': sell_amount,
            'cost_of_sold': cost_of_sold,
            'profit': profit
        }
        state['profit_history'].append(profit_info)
        
        return {
            'action': 'sell',
            'symbol': symbol,
            'size': sell_shares,
            'amount': sell_amount,
            'price': current_price,
            'current_return': current_return,
            'profit': profit
        }
    
    def get_portfolio_status(self, symbol, current_price):
        """获取投资组合状态"""
        state = self.symbol_states[symbol]
        current_value = state['total_shares'] * current_price
        
        if state['total_invested'] > 0:
            current_return = (current_value - state['total_invested']) / state['total_invested'] * 100
        else:
            current_return = 0
        
        total_assets = current_value + state['total_sell_amount']
        total_investment = sum([inv['amount'] for inv in state['investment_history']])
        
        if total_investment > 0:
            total_return = ((total_assets - total_investment) / total_investment) * 100
        else:
            total_return = 0
        
        return {
            'symbol': symbol,
            'investment_count': state['investment_count'],
            'total_shares': state['total_shares'],
            'total_invested': state['total_invested'],
            'current_value': current_value,
            'current_return': current_return,
            'total_investment': total_investment,
            'total_sell_amount': state['total_sell_amount'],
            'total_assets': total_assets,
            'total_return': total_return,
            'last_investment_date': state['last_investment_date']
        }
    
    def get_total_portfolio_value(self, current_prices):
        """获取总投资组合价值"""
        total_value = 0
        for symbol in self.symbols:
            state = self.symbol_states[symbol]
            if symbol in current_prices:
                total_value += state['total_shares'] * current_prices[symbol] + state['total_sell_amount']
        return total_value
    
    def to_dict(self):
        """转换为字典 - 安全的JSON序列化"""
        serialized_states = {}
        
        for symbol, state in self.symbol_states.items():
            # 序列化日期字段
            last_investment_date = state['last_investment_date']
            last_profit_taking_date = state['last_profit_taking_date']
            
            # 处理日期序列化
            if last_investment_date and hasattr(last_investment_date, 'isoformat'):
                last_investment_date = last_investment_date.isoformat()
            if last_profit_taking_date and hasattr(last_profit_taking_date, 'isoformat'):
                last_profit_taking_date = last_profit_taking_date.isoformat()
            
            serialized_states[symbol] = {
                'investment_count': state['investment_count'],
                'last_investment_date': last_investment_date,
                'last_profit_taking_date': last_profit_taking_date,
                'total_invested': state['total_invested'],
                'total_shares': state['total_shares'],
                'total_sell_amount': state['total_sell_amount'],
                'investment_history': state['investment_history'],
                'profit_history': state['profit_history']
            }
        
        return {
            'symbols': self.symbols,
            'symbol_states': serialized_states
        }
    
    def from_dict(self, data):
        """从字典加载 - 安全的JSON反序列化"""
        self.symbols = data.get('symbols', self.symbols)
        raw_states = data.get('symbol_states', {})
        
        self.symbol_states = {}
        for symbol in self.symbols:
            if symbol in raw_states:
                raw_state = raw_states[symbol]
                
                # 反序列化日期字段
                last_investment_date = None
                last_profit_taking_date = None
                
                if raw_state.get('last_investment_date'):
                    try:
                        last_investment_date = datetime.fromisoformat(raw_state['last_investment_date']).date()
                    except (ValueError, TypeError):
                        last_investment_date = None
                
                if raw_state.get('last_profit_taking_date'):
                    try:
                        last_profit_taking_date = datetime.fromisoformat(raw_state['last_profit_taking_date']).date()
                    except (ValueError, TypeError):
                        last_profit_taking_date = None
                
                self.symbol_states[symbol] = {
                    'investment_count': raw_state.get('investment_count', 0),
                    'last_investment_date': last_investment_date,
                    'last_profit_taking_date': last_profit_taking_date,
                    'total_invested': raw_state.get('total_invested', 0.0),
                    'total_shares': raw_state.get('total_shares', 0.0),
                    'total_sell_amount': raw_state.get('total_sell_amount', 0.0),
                    'investment_history': raw_state.get('investment_history', []),
                    'profit_history': raw_state.get('profit_history', [])
                }
            else:
                # 初始化新币种状态
                self.symbol_states[symbol] = {
                    'investment_count': 0,
                    'last_investment_date': None,
                    'last_profit_taking_date': None,
                    'total_invested': 0.0,
                    'total_shares': 0.0,
                    'total_sell_amount': 0.0,
                    'investment_history': [],
                    'profit_history': []
                }