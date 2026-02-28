from aiogram.fsm.state import State, StatesGroup

class DebtStates(StatesGroup):
    waiting_for_customer_name = State()
    waiting_for_amount = State()
    waiting_for_sub_amount = State()
