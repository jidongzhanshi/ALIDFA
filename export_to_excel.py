import pandas as pd
import json
from datetime import datetime
import os

def export_strategy_to_excel():
    """将策略数据导出到Excel"""
    
    # 读取策略状态
    with open('data/multi_strategy_state.json', 'r', encoding='utf-8') as f:
        strategy_data = json.load(f)
    
    # 创建Excel文件
    with pd.ExcelWriter('strategy_export.xlsx', engine='openpyxl') as writer:
        
        # 导出投资历史
        all_investments = []
        for symbol, state in strategy_data['symbol_states'].items():
            for inv in state['investment_history']:
                inv_record = inv.copy()
                inv_record['币种'] = symbol
                all_investments.append(inv_record)
        
        if all_investments:
            investment_df = pd.DataFrame(all_investments)
            investment_df = investment_df.rename(columns={
                'date': '日期', 'price': '价格', 'amount': '金额',
                'shares': '数量', 'deviation': '偏离度', 'multiplier': '倍数'
            })
            investment_df.to_excel(writer, sheet_name='投资历史', index=False)
        
        # 导出持仓汇总
        portfolio_data = []
        for symbol, state in strategy_data['symbol_states'].items():
            portfolio_data.append({
                '币种': symbol,
                '投资期数': state['investment_count'],
                '持仓数量': state['total_shares'],
                '持仓成本': state['total_invested'],
                '累计投资': sum([inv['amount'] for inv in state['investment_history']]),
                '累计卖出': state['total_sell_amount']
            })
        
        portfolio_df = pd.DataFrame(portfolio_data)
        portfolio_df.to_excel(writer, sheet_name='持仓汇总', index=False)
        
        # 导出止盈历史
        all_profits = []
        for symbol, state in strategy_data['symbol_states'].items():
            for profit in state['profit_history']:
                profit_record = profit.copy()
                profit_record['币种'] = symbol
                all_profits.append(profit_record)
        
        if all_profits:
            profit_df = pd.DataFrame(all_profits)
            profit_df = profit_df.rename(columns={
                'date': '日期', 'price': '卖出价格', 'shares_sold': '卖出数量',
                'amount_received': '卖出金额', 'profit': '实际收益',
                'return_percent': '收益率'
            })
            profit_df.to_excel(writer, sheet_name='止盈历史', index=False)
    
    print("✅ 策略数据已导出到 strategy_export.xlsx")

if __name__ == '__main__':
    export_strategy_to_excel()