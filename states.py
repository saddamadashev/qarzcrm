from aiogram.fsm.state import StatesGroup, State

class AddCustomer(StatesGroup):
    waiting_name = State()

class AddTransaction(StatesGroup):
    waiting_customer = State()
    waiting_amount = State()