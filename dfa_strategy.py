import json
from datetime import datetime

class DFAStrategyLogic:
    def __init__(self, base_cash=70, investment_interval=14, target_return=75, 
                 sell_ratio=0.5, profit_taking_cooldown=30):
        self.base_cash = base_cash
        self.investment_interval = investment_interval
        self.target_return = target_return
        self.sell_ratio = sell_ratio
        self.profit_taking_cooldown = profit_taking_cooldown
        
        self.investment_count = 0
        self.last_investment_date = None
        self.last_profit_taking_date = None
        self.total_invested = 0.0
        self.total_shares = 0.0
        self.total_sell_amount = 0.0
        self.investment_history = []
        self.profit_history = []
    
    def get_investment_multiplier(self, deviation):
        if deviation <= -20: return 2.2
        elif deviation <= -10: return 1.8
        elif deviation <= 0: return 1.4
        elif deviation <= 5: return 1.0
        elif deviation <= 15: return 0.5
        elif deviation <= 25: return 0.2
        else: return 0.0
    
    def calculate_deviation(self, current_price, ma120_value):
        if ma120_value == 0:
            return 0
        return (current_price - ma120_value) / ma120_value * 100
    
    def should_invest_today(self, current_date):
        if self.last_investment_date is None:
            return True
        days_since_last = (current_date - self.last_investment_date).days
        return days_since_last >= self.investment_interval
    
    def should_take_profit(self, current_date, current_return):
        if current_return < self.target_return:
            return False
        if self.last_profit_taking_date is not None:
            days_since_last = (current_date - self.last_profit_taking_date).days
            if days_since_last < self.profit_taking_cooldown:
                return False
        return True
    
    def execute_investment(self, current_price, ma120_value, current_date, available_cash=None):
        deviation = self.calculate_deviation(current_price, ma120_value)
        multiplier = self.get_investment_multiplier(deviation)
        investment_amount = self.base_cash * multiplier
        
        if available_cash is not None and investment_amount > available_cash:
            investment_amount = available_cash
        
        if investment_amount <= 0:
            return {'action': 'skip', 'reason': f'偏离度 {deviation:.1f}%，暂停投资'}
        
        size = round(investment_amount / current_price, 4)
        if size <= 0:
            return {'action': 'skip', 'reason': '计算出的购买数量为0'}
        
        actual_invested = size * current_price
        self.total_invested += actual_invested
        self.total_shares += size
        self.investment_count += 1
        self.last_investment_date = current_date
        
        investment_info = {
            'date': current_date.isoformat(),
            'price': current_price,
            'ma120': ma120_value,
            'deviation': deviation,
            'multiplier': multiplier,
            'amount': actual_invested,
            'shares': size
        }
        self.investment_history.append(investment_info)
        
        return {
            'action': 'buy',
            'size': size,
            'amount': actual_invested,
            'price': current_price,
            'deviation': deviation,
            'multiplier': multiplier
        }
    
    def execute_profit_taking(self, current_price, current_date):
        if self.total_shares <= 0:
            return {'action': 'skip', 'reason': '暂无持仓'}
        
        current_value = self.total_shares * current_price
        if self.total_invested > 0:
            current_return = (current_value - self.total_invested) / self.total_invested * 100
        else:
            current_return = 0
        
        if not self.should_take_profit(current_date, current_return):
            return {'action': 'skip', 'reason': f'收益率{current_return:.1f}%未达标'}
        
        sell_shares = round(self.total_shares * self.sell_ratio, 4)
        if sell_shares <= 0:
            return {'action': 'skip', 'reason': '计算出的卖出数量为0'}
        
        sell_amount = sell_shares * current_price
        cost_of_sold = (sell_shares / self.total_shares) * self.total_invested
        profit = sell_amount - cost_of_sold
        
        self.total_shares -= sell_shares
        self.total_invested -= cost_of_sold
        self.total_sell_amount += sell_amount
        self.last_profit_taking_date = current_date
        
        profit_info = {
            'date': current_date.isoformat(),
            'price': current_price,
            'return_percent': current_return,
            'shares_sold': sell_shares,
            'amount_received': sell_amount,
            'cost_of_sold': cost_of_sold,
            'profit': profit
        }
        self.profit_history.append(profit_info)
        
        return {
            'action': 'sell',
            'size': sell_shares,
            'amount': sell_amount,
            'price': current_price,
            'current_return': current_return,
            'profit': profit
        }
    
    def to_dict(self):
        return {
            'investment_count': self.investment_count,
            'last_investment_date': self.last_investment_date.isoformat() if self.last_investment_date else None,
            'last_profit_taking_date': self.last_profit_taking_date.isoformat() if self.last_profit_taking_date else None,
            'total_invested': self.total_invested,
            'total_shares': self.total_shares,
            'total_sell_amount': self.total_sell_amount,
            'investment_history': self.investment_history,
            'profit_history': self.profit_history
        }
    
    def from_dict(self, data):
        self.investment_count = data.get('investment_count', 0)
        self.last_investment_date = datetime.fromisoformat(data['last_investment_date']) if data.get('last_investment_date') else None
        self.last_profit_taking_date = datetime.fromisoformat(data['last_profit_taking_date']) if data.get('last_profit_taking_date') else None
        self.total_invested = data.get('total_invested', 0.0)
        self.total_shares = data.get('total_shares', 0.0)
        self.total_sell_amount = data.get('total_sell_amount', 0.0)
        self.investment_history = data.get('investment_history', [])
        self.profit_history = data.get('profit_history', [])