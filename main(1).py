import asyncio
import spade
from spade.agent import Agent
from spade.behaviour import FSMBehaviour, State, CyclicBehaviour, PeriodicBehaviour, OneShotBehaviour
from spade.message import Message
import time
import random
from queue import Queue
import matplotlib.pyplot as plt
import numpy as np
from threading import Thread


class BaseAgent(Agent):
    """Base class for all agents"""

    def __init__(self, strategy, risk, jid: str, password: str):
        super().__init__(jid, password)
        self.strategy = strategy
        self.risk = risk
        self.portfolio = Portfolio()
        self.strategy = strategy
        print(jid + " started")

    def get_strategy(self):
        return self.strategy

    def get_portfolio(self):
        return self.portfolio

    def get_balance(self):
        return self.portfolio.balance

    def get_stocks_owned(self):
        return self.portfolio.stocks_owned

    def get_num_stocks_bought(self):
        return self.portfolio.num_stocks_bought

    def update_portfolio(self, company, quantity, price):
        self.portfolio.balance -= quantity * price
        self.portfolio.stocks_owned[company] = quantity
        self.portfolio.num_stocks_bought += quantity

    async def setup(self):
        self.add_behaviour(self.TransactionConfirmationBehav())

    class TransactionConfirmationBehav(CyclicBehaviour):
        async def run(self):
            await asyncio.sleep(1)
            await self.make_buy_order()
            await self.go()
            if not (self.agent.portfolio.is_empty()):
                self.sell_stocks()

                await self.go()

        async def go(self):
            for i in range(self.mailbox_size()):
                msg = await self.receive(timeout=2)
                mensa = msg.body.split(" ")
                if mensa[1] == "bought":
                    # ['1@localhost', 'bought', '69', 'stocks', 'of', 'GHI', 'for', '690']
                    self.agent.portfolio.update_stocks_owned(mensa[5], int(mensa[2]), int(mensa[7]))
                    self.agent.portfolio.add_money(int(mensa[7]) * int(mensa[2]) * (-1))
                    self.agent.portfolio.update_num_stocks_bought(int(mensa[2]))
                elif mensa[1] == "sold":
                    # ['2@localhost', 'sold', '0', 'stocks', 'of', 'GHI', 'for', '0']
                    self.agent.portfolio.update_stocks_owned(mensa[5], int(mensa[2]), int(mensa[7]))
                    self.agent.portfolio.add_money(int(mensa[7]) * int(mensa[2]))
                    self.agent.portfolio.update_num_stocks_bought(int(mensa[2]))
                    self.agent.portfolio.temp_balance += int(mensa[7]) * int(mensa[2])
                elif mensa[0] == "Hey":
                    self.agent.portfolio.temp_balance += int(mensa[-1])

        async def make_buy_order(self):
            # Strategy 1 - Buy from the company with the best reputation
            if self.agent.strategy == 1:
                best_reputation_companies = [company for company, reputation in environment.company_reputation.items()
                                             if reputation == max(environment.company_reputation.values())]

                #  In case of a draw, buy from the cheapest company
                cheapest_price = float('inf')
                for company in best_reputation_companies:
                    price = environment.get_company_price(company)
                    if price < cheapest_price:
                        cheapest_price = price
                        selected_company = company

                # Calculate the quantity to buy based on available balance and risk
                current_price = environment.get_company_price(selected_company)
                max_expense = int(self.agent.portfolio.temp_balance * ((((self.agent.risk - 1) / 4) * 0.80) + 0.1))
                max_quantity = int(max_expense / current_price)

                # Make the buy order
                if max_quantity > 0:
                    q_rand = random.randint(1, max_quantity)
                    # Inform the manager that the agent wants to buy
                    msg = Message(to="manager@localhost")
                    msg.set_metadata("performative", "inform")
                    msg.body = f"{self.agent.jid},{self.agent.portfolio.temp_balance},{selected_company},{q_rand},{current_price}"
                    self.agent.portfolio.temp_balance += -q_rand * current_price
                    await self.send(msg)

            # Strategy 2 - Buy from the company with the best price variation according to price history
            elif self.agent.strategy == 2:
                max_variance = -1
                for c in environment.companies.keys():
                    if len(environment.historical_data[c]) > 1:
                        old_price = environment.historical_data[c][-2]
                        new_price = environment.get_company_price(c)
                        variation = (new_price - old_price)
                        if variation > 0:
                            if variation > max_variance:
                                max_variance = variation
                                company_best_price = c

                if max_variance > 0:
                    current_price = environment.get_company_price(company_best_price)
                    max_expense = int(self.agent.portfolio.temp_balance * ((((self.agent.risk - 1) / 4) * 0.80) + 0.1))
                    max_quantity = int(max_expense / current_price)

                    if max_quantity > 0:
                        q_rand = random.randint(1, max_quantity)
                        # Inform the manager that the agent wants to buy
                        msg = Message(to="manager@localhost")
                        msg.set_metadata("performative", "inform")
                        msg.body = f"{self.agent.jid},{self.agent.portfolio.temp_balance},{company_best_price},{q_rand},{current_price}"
                        self.agent.portfolio.temp_balance += -q_rand * current_price
                        await self.send(msg)

            # Strategy 3 - Mix of the previous 2 strategies
            elif self.agent.strategy == 3:
                # Select the 3 companies  with the best reputation
                best_reputation_companies = []
                max_variance = -1

                sorted_reputation = list(
                    sorted(environment.company_reputation.items(), key=lambda x: x[1], reverse=True))
                for i in range(3):
                    best_reputation_companies.append(sorted_reputation[i][0])

                # Select the company with the best price variation among the 3 companies with the best reputation
                for c in best_reputation_companies:
                    if len(environment.historical_data[c]) > 1:
                        old_price = environment.historical_data[c][-2]
                        new_price = environment.get_company_price(c)
                        variation = (new_price - old_price)
                        if variation > 0:
                            if variation > max_variance:
                                max_variance = variation
                                company_best_price = c

                if max_variance > 0:
                    current_price = environment.get_company_price(company_best_price)
                    max_expense = int(self.agent.portfolio.temp_balance * ((((self.agent.risk - 1) / 4) * 0.80) + 0.1))
                    max_quantity = int(max_expense / current_price)

                    if max_quantity > 0:
                        q_rand = random.randint(1, max_quantity)
                        # Inform the manager that the agent wants to buy
                        msg = Message(to="manager@localhost")
                        msg.set_metadata("performative", "inform")
                        msg.body = f"{self.agent.jid},{self.agent.portfolio.temp_balance},{company_best_price},{q_rand},{current_price}"
                        self.agent.portfolio.temp_balance += -q_rand * current_price
                        await self.send(msg)

            # Strategy 4 - Buy from the cheapest company
            elif self.agent.strategy == 4:

                #  In case of a draw, buy from the cheapest company
                cheapest_price = float('inf')
                for company in environment.companies.keys():
                    price = environment.get_company_price(company)
                    if price < cheapest_price:
                        cheapest_price = price
                        selected_company = company

                # Calculate the quantity to buy based on available balance and risk
                current_price = environment.get_company_price(selected_company)
                max_expense = int(self.agent.portfolio.temp_balance * ((((self.agent.risk - 1) / 4) * 0.80) + 0.1))
                max_quantity = int(max_expense / current_price)

                # Make the buy order
                if max_quantity > 0:
                    q_rand = random.randint(1, max_quantity)
                    # Inform the manager that the agent wants to buy
                    msg = Message(to="manager@localhost")
                    msg.set_metadata("performative", "inform")
                    msg.body = f"{self.agent.jid},{self.agent.portfolio.temp_balance},{selected_company},{q_rand},{current_price}"
                    self.agent.portfolio.temp_balance += -q_rand * current_price
                    await self.send(msg)

            # Strategy Random - Buy from a random company a random quantity of stocks
            else:
                company = random.choice(list(environment.get_companies()))

                current_price = environment.get_company_price(company)
                max_expense = int(self.agent.portfolio.temp_balance * ((((self.agent.risk - 1) / 4) * 0.80) + 0.1))
                max_quantity = int(max_expense / current_price)

                if max_quantity > 0:
                    q_random = random.randint(1, max_quantity)

                    # Make the buy order
                    # Inform the manager that the agent wants to buy
                    msg = Message(to="manager@localhost")
                    msg.set_metadata("performative", "inform")
                    msg.body = f"{self.agent.jid},{self.agent.portfolio.temp_balance},{company},{q_random},{current_price}"
                    self.agent.portfolio.temp_balance += -q_random * current_price
                    await self.send(msg)

        def sell_stocks(self):
            # Sell the stocks where the current price is higher than the price when the stocks were bought
            # Higher risk means that the agent will only sell if the price is 90% higher than the price when the stocks were bought
            # Lower risk means that the agent will sell if the price is 10% higher than the price when the stocks were bought
            for c in self.agent.portfolio.stocks_owned.keys():
                if self.agent.portfolio.stocks_owned[c][0] > 0:
                    new_price = environment.get_company_price(c)
                    old_price = self.agent.portfolio.get_old_price(c)
                    variation = (new_price - old_price)
                    if variation > 0:
                        sell_random = random.randint(1, self.agent.portfolio.stocks_owned[c][0])
                        environment.append_to_sell(c, self.agent.jid, sell_random)


class Portfolio:
    """Class that represents the portfolio of a stock market agent"""

    def __init__(self, initial_balance=0):
        self.balance = initial_balance
        self.temp_balance = initial_balance
        self.stocks_owned = {}  # Dictionary to track owned stocks {company_name: [quantity, old_price]}
        self.num_stocks_bought = 0  # Total number of stocks bought

    def add_money(self, amount):
        self.balance += amount

    def update_stocks_owned(self, company, quantity, price):
        if company in self.stocks_owned.keys():
            self.stocks_owned[company][0] += quantity
            self.stocks_owned[company][1] = price
        else:
            # needs to have the price of the company of the moment of the transaction
            self.stocks_owned[company] = [quantity, price]

    def update_price(self, company, price):
        self.stocks_owned[company][1] = price

    def update_num_stocks_bought(self, quantity):
        self.num_stocks_bought += quantity

    def get_balance(self):
        return self.balance

    def get_stocks_owned(self):
        return self.stocks_owned

    def get_num_stocks_bought(self):
        return self.num_stocks_bought

    def get_company(self, o):
        aux = list(self.stocks_owned.keys())
        return aux[o]

    def is_empty(self):
        return self.stocks_owned == {}

    def get_old_price(self, company):
        return self.stocks_owned[company][1]


class Environment:
    """each company is a dict where the key is the string of the company name and the value is a list of the products
    with the price and quantity of stocks """

    def __init__(self):
        # we use a dict where: key = company name and value: [n_stocks, price]
        self.companies = {}
        # we use a dict where: key = company and value: [[seller, quantity],[seller, quantity]], ...
        self.to_sell = {"test": []}
        # Historical data storage for companies
        self.historical_data = {}  # {company_name: [price1, price2, ...]}
        # Reputation factor for each company
        self.company_reputation = {}  # {company_name: reputation}
        # Number of stocks sold by a company
        self.quantity_sold = {}  # {company_name: [q, total]}

    def average_price(self, company):
        historical_prices = 0
        # Calculate the average price for a company
        for c in self.companies[company]:
            historical_prices += c

        return int(historical_prices / len(self.companies[company]))

    def update_company_price(self, company, new_price):
        # Update the price for a company
        self.companies[company][1] = new_price

        # Update historical data
        if company not in self.historical_data:
            self.historical_data[company] = []
        if new_price != self.historical_data[company][-1]:
            self.historical_data[company].append(new_price)

        # Keep historical data length limited if needed
        if len(self.historical_data[company]) > 5:
            self.historical_data[company].pop(0)

    def calculate_sold_stocks_based_change(self, company, quantity_sold, total):
        # Calculate the change in price based on the number of stocks sold
        # The more stocks are sold, the higher the price will be
        if company in self.companies:
            current_price = self.companies[company][1]
            r = random.randint(int(environment.company_reputation[company]*100), 100)
            r = r/100
            cut_price = r*0.02* current_price
            r_cut_price = random.randint(-1, 1) * cut_price
            price_change = 0
            if total != 0:
                percentage_sold = (quantity_sold / total)
                if percentage_sold < 0.10:
                    price_change = 0.95
                    new_price = current_price*price_change + r_cut_price
                    new_price = int(new_price)
                else:
                    price_change = 1.05
                    new_price = current_price*price_change + r_cut_price
                    new_price = int(new_price)
                if new_price == 0:
                    new_price = 1
                return new_price
            else:
                if quantity_sold > 0:
                    price_change = 1.05
                    new_price = current_price*price_change + r_cut_price
                    new_price = int(new_price)
                    return new_price
                else:
                    price_change = 0.95
                    new_price = current_price*price_change + r_cut_price
                    new_price = int(new_price)
                    if new_price == 0:
                        new_price = 1
                    return new_price

    def random_reputation_change(self, company):
        # Randomly change the reputation of a company
        # Reputation can be a value between 0 and 1
        # 0 means that the company is not reliable and 1 means that the company is very reliable
        # Keep in mind that this is a pseudo-random change
        if company in self.company_reputation:
            reputation = self.company_reputation[company]
            reputation_change = random.randint(-1, 1) * 0.1
            new_reputation = reputation + reputation_change
            if new_reputation < 0:
                new_reputation = 0
            elif new_reputation > 1:
                new_reputation = 1
            self.company_reputation[company] = new_reputation

    def create_companies(self, company, n_stocks, price, reputation):
        self.companies[company] = [n_stocks, price]
        self.quantity_sold[company] = [0, n_stocks]
        self.historical_data[company] = [price]
        self.company_reputation[company] = reputation

    def append_to_sell(self, company, seller, quantity):
        if company in self.to_sell.keys():
            self.to_sell[company].append([seller, quantity])
            self.to_sell[company].sort(key=lambda x: x[1], reverse=True)
        else:
            self.to_sell[company] = [[seller, quantity]]

    def reorder_sellers(self, company):
        self.to_sell[company].sort(key=lambda x: x[1], reverse=True)

    def get_companies(self):
        return self.companies.keys()

    def get_company_price(self, company):
        return self.companies[company][1]

    def get_company_stocks(self, company):
        return self.companies[company][0]

    def get_company(self, o):
        aux = list(self.companies.keys())
        return aux[o]

    # this method removes the negative and 0 values from the sellers dict
    def remove_from_sellers(self, company):
        # start from the end of the list, since this method will only be used after the reorder method
        for i in range(len(self.to_sell[company]) - 1, -1, -1):
            if self.to_sell[company][i][1] <= 0:
                self.to_sell[company].pop(i)
            else:
                # if the value is positive, we can stop the loop
                break


# global variable. We initialize it in ths part of the code because we need to use it in the main function
environment = Environment()


class ManagerAgent(Agent):
    """Agent that manages the selling and buying of stocks"""

    def __init__(self):
        super().__init__("manager@localhost", "password")
        print("manager@localhost started")

    async def setup(self):
        b = self.ManagingCycle(4)
        self.add_behaviour(b)

    class ManagingCycle(PeriodicBehaviour):

        async def run(self):
            print("ManagingCycle behavior is running")
            for i in range(self.mailbox_size()):
                await self.match_order()
            for c in environment.companies:
                # Update company prices based on reputation
                environment.update_company_price(c,environment.calculate_sold_stocks_based_change(c, environment.quantity_sold[c][0], environment.quantity_sold[c][1]))
                environment.quantity_sold[c][0] = 0
                environment.quantity_sold[c][1] = environment.companies[c][0]
                environment.random_reputation_change(c)

        async def match_order(self):
            order = await self.receive(timeout=2)
            buyer, money_buy, company_buy, quantity_buy, price_atm = order.body.split(",")
            money_buy = int(money_buy)
            quantity_buy = int(quantity_buy)
            tmp_q = quantity_buy
            price_atm = int(price_atm)
            # the manager checks directly if either a company or the seller(dict) has what the buyer wants
            # starts by checking if the buyer has money
            if money_buy >= environment.get_company_price(company_buy) * quantity_buy:
                if environment.get_company_stocks(company_buy) >= quantity_buy:
                    # Match found
                    # Inform the buyer that the order was successful
                    environment.quantity_sold[company_buy][0] += quantity_buy
                    msg = Message(to=str(buyer))
                    msg.set_metadata("performative", "inform")
                    msg.body = f"{str(buyer)} bought {quantity_buy} stocks of {company_buy} for {environment.get_company_price(company_buy)} each"
                    message_log.append(msg.body)
                    await self.send(msg)
                    # Update the company stocks
                    environment.companies[company_buy][0] -= quantity_buy
                else:
                    # No match found
                    # Check the sellers_dict
                    # This is possible because the values inside the dict are organized by quantity
                    soma = 0

                    # We need to check if the company exists inside the sellers dict
                    if company_buy not in environment.to_sell:
                        # Inform the buyer that the order was unsuccessful
                        msg = Message(to=str(buyer))
                        msg.set_metadata("performative", "inform")
                        msg.body = f"Hey {str(buyer)}, we don't have any sellers for {company_buy} {quantity_buy * price_atm}"
                        message_log.append(msg.body)
                        await self.send(msg)
                        return
                    selers = []
                    for i in range(len(environment.to_sell[company_buy])):
                        if str(environment.to_sell[company_buy][i][0]) != str(buyer):
                            soma += environment.to_sell[company_buy][i][1]
                            selers.append(i)
                        if soma >= quantity_buy:
                            # Match found
                            # Update the sellers dict
                            for j in range(len(selers) - 1):
                                # Message the seller that he did a successful sell
                                w = selers[j]
                                msg = Message(to=str(environment.to_sell[company_buy][w][0]))
                                msg.set_metadata("performative", "inform")
                                msg.body = f"{str(environment.to_sell[company_buy][w][0])} sold {environment.to_sell[company_buy][w][1]} stocks of {company_buy} for {environment.get_company_price(company_buy)} each"
                                message_log.append(msg.body)
                                await self.send(msg)
                                quantity_buy -= environment.to_sell[company_buy][w][1]
                                environment.to_sell[company_buy][w][1] = 0

                            # Inform the i seller that he did a successful sell
                            environment.to_sell[company_buy][i][1] -= quantity_buy
                            msg = Message(to=str(environment.to_sell[company_buy][i][0]))
                            msg.set_metadata("performative", "inform")
                            msg.body = f"{str(environment.to_sell[company_buy][i][0])} sold {quantity_buy} stocks of {company_buy} for {environment.get_company_price(company_buy)} each"
                            message_log.append(msg.body)
                            await self.send(msg)

                            # Reorder and remove the sellers that have 0 or negative values
                            environment.reorder_sellers(company_buy)
                            environment.remove_from_sellers(company_buy)

                            # Inform the buyer that the order was successful
                            environment.quantity_sold[company_buy][0] += tmp_q
                            msg = Message(to=str(buyer))
                            msg.set_metadata("performative", "inform")
                            msg.body = f"{str(buyer)} bought {quantity_buy} stocks of {company_buy} for {environment.get_company_price(company_buy)} each"
                            message_log.append(msg.body)
                            await self.send(msg)
                            quantity_buy = 0
                            return

                    # If we reach this point, it means that there are not enough sellers for the order
                    # Inform the buyer that the order was unsuccessful
                    msg = Message(to=str(buyer))
                    msg.set_metadata("performative", "inform")
                    msg.body = f"Hey {str(buyer)}, we don't have enough sellers for {company_buy} {quantity_buy * price_atm}"
                    message_log.append(msg.body)
                    await self.send(msg)
            else:
                # No money
                # Inform the buyer that the order was unsuccessful
                msg = Message(to=str(buyer))
                msg.set_metadata("performative", "inform")
                msg.body = f"Sorry, you don't have enough money to buy {quantity_buy} stocks of {company_buy}"
                message_log.append(msg.body)
                await self.send(msg)


async def live_plotting():
    num_companies = len(environment.companies)
    num_agents = len(agents)  # Assuming agents list is accessible here
    time_values = []
    variable_values_quantity = [[] for _ in range(num_companies)]
    variable_values_prices = [[] for _ in range(num_companies)]
    variable_values_money = [[] for _ in range(num_agents)]

    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(10, 10))
    plt.ion()
    plt.tight_layout()

    MAX_X_VALUES = 10
    while True:
        time_values.append(len(time_values) + 1)  # Assuming time increases by 1 every second

        for i, company in enumerate(environment.companies):
            # Get stock quantity and price for each company
            quantity = environment.companies[company][0]
            price = environment.companies[company][1]

            # Update values for quantity and prices
            variable_values_quantity[i].append(quantity)
            variable_values_prices[i].append(price)

        # Track agent money over time
        for i, agent in enumerate(agents):
            money = agent.portfolio.balance
            variable_values_money[i].append(money)

        # Update x-axis limits to create a rolling window effect
        start_x = max(0, len(time_values) - MAX_X_VALUES)  # Start of the rolling window
        end_x = len(time_values)  # End of the rolling window
        ax1.set_xlim(start_x, end_x)
        ax2.set_xlim(start_x, end_x)
        ax3.set_xlim(start_x, end_x)
        ax4.set_xlim(start_x, end_x)

        # Plot quantities of stock for each company
        ax1.clear()
        for i, var in enumerate(variable_values_quantity):
            ax1.plot(time_values[max(0, len(time_values) - MAX_X_VALUES):],
                     var[max(0, len(time_values) - MAX_X_VALUES):], '-o',
                     label=f'{list(environment.companies.keys())[i]}')
        ax1.legend()
        ax1.set_ylabel('Quantity')
        ax1.set_title('Stock Quantity of Companies over Time')

        # Clear and plot prices for all companies as a subplot
        ax2.clear()
        for i, var in enumerate(variable_values_prices):
            ax2.plot(time_values[max(0, len(time_values) - MAX_X_VALUES):],
                     var[max(0, len(time_values) - MAX_X_VALUES):], '-o',
                     label=f'{list(environment.companies.keys())[i]}')
        ax2.legend()
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Stock Price')
        ax2.set_title('Stock Price of Companies over Time')

        # For the 3rd plot - Money of each Agent over Time
        ax3.clear()
        for i, var in enumerate(variable_values_money):
            ax3.plot(time_values[max(0, len(time_values) - MAX_X_VALUES):],
                     var[max(0, len(time_values) - MAX_X_VALUES):], '-o',
                     label=f'Agent {i + 1}')
        ax3.legend()
        ax3.set_xlabel('Time')
        ax3.set_ylabel('Money')
        ax3.set_title('Agent Money over Time')

        # For the 4th plot - Message Log
        ax4.clear()
        ax4.axis('off')  # Hide the axes for the log subplot
        ax4.text(0.05, 0.95, "Message Log:", verticalalignment='top', transform=ax4.transAxes, fontsize=10,
                 weight='bold')

        # Display the log messages in the ax4 subplot
        log_text = '\n'.join(message_log[-MAX_X_VALUES:])  # Get the last MAX_X_VALUES messages
        ax4.text(0.05, 0.85, log_text, verticalalignment='top', transform=ax4.transAxes, fontsize=15,
                 family='monospace')

        plt.pause(0.1)
        await asyncio.sleep(1)


def start_plotting(self):
    plot_thread = Thread(target=self.update_plot)
    plot_thread.start()


async def main():
    global environment

    environment = Environment()
    environment.create_companies("APPLE", 70, 100, 0.5)
    environment.create_companies("GOOGLE", 40, 100, 0.8)
    environment.create_companies("AMAZON", 75, 150, 0.5)
    environment.create_companies("TESLA", 60, 160, 0.5)
    environment.create_companies("SONY", 50, 110, 0.8)
    environment.create_companies("COCACOLA", 75, 150, 0.5)
    environment.create_companies("WORTEN", 60, 110, 0.2)
    environment.create_companies("FNAC", 55, 110, 0.6)

    print(environment.get_companies())

    # Create and start agents
    global agents
    global message_log
    agents = []
    message_log = []

    # Create and start manager agent
    manager_a = ManagerAgent()
    agent1 = BaseAgent(1, 3, "1@localhost", "123")
    agent1.get_portfolio().balance = 5000
    agent1.get_portfolio().temp_balance = 5000

    agent2 = BaseAgent(1, 1, "2@localhost", "123")
    agent2.get_portfolio().balance = 6000
    agent2.get_portfolio().temp_balance = 6000

    agent3 = BaseAgent(2, 2, "3@localhost", "123")
    agent3.get_portfolio().balance = 5000
    agent3.get_portfolio().temp_balance = 5000

    agent4 = BaseAgent(2, 4, "4@localhost", "123")
    agent4.get_portfolio().balance = 6000
    agent4.get_portfolio().temp_balance = 6000

    agent5 = BaseAgent(3, 1, "5@localhost", "123")
    agent5.get_portfolio().balance = 5000
    agent5.get_portfolio().temp_balance = 5000

    agent6 = BaseAgent(3, 5, "6@localhost", "123")
    agent6.get_portfolio().balance = 6000
    agent6.get_portfolio().temp_balance = 6000

    agent7 = BaseAgent(4, 2, "7@localhost", "123")
    agent7.get_portfolio().balance = 4000
    agent7.get_portfolio().temp_balance = 4000

    agent8 = BaseAgent(4, 2, "8@localhost", "123")
    agent8.get_portfolio().balance = 4000
    agent8.get_portfolio().temp_balance = 4000

    agent9 = BaseAgent(0, 1, "9@localhost", "123")
    agent9.get_portfolio().balance = 6000
    agent9.get_portfolio().temp_balance = 6000

    agent10 = BaseAgent(0, 3, "10@localhost", "123")
    agent10.get_portfolio().balance = 5000
    agent10.get_portfolio().temp_balance = 5000

    agent11 = BaseAgent(4, 4, "11@localhost", "123")
    agent11.get_portfolio().balance = 5100
    agent11.get_portfolio().temp_balance = 5100

    agent12 = BaseAgent(4, 5, "120@localhost", "123")
    agent12.get_portfolio().balance = 5000
    agent12.get_portfolio().temp_balance = 5000

    agents.append(agent1)
    agents.append(agent2)
    agents.append(agent3)
    agents.append(agent4)
    agents.append(agent5)
    agents.append(agent6)
    agents.append(agent7)
    agents.append(agent8)
    agents.append(agent9)
    agents.append(agent10)
    agents.append(agent11)
    agents.append(agent12)

    await manager_a.start(auto_register=True)
    for agent in agents:
        await agent.start(auto_register=True)


    await live_plotting()


if __name__ == "__main__":
    asyncio.run(main())
