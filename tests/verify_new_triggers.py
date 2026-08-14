from aiogram import F
from aiogram.types import Message
from unittest.mock import Mock

def test_filters():
    print("Testing filters...")
    
    msg = Mock(spec=Message)
    
    # Test 1: Upkatana
    f_upkatana = F.text.lower().in_({"ап катана", "\\upkatana"})
    
    msg.text = "ап катана"
    res = f_upkatana.resolve(msg)
    print(f"upkatana('ап катана') = {res}")
    assert res
    
    msg.text = "other"
    res = f_upkatana.resolve(msg)
    print(f"upkatana('other') = {res}")
    assert not res
    
    # Test 2: Profile
    f_profile = F.text.lower() == "мой сенсей"
    
    msg.text = "мой сенсей"
    res = f_profile.resolve(msg)
    print(f"profile('мой сенсей') = {res}")
    assert res
    
    msg.text = "other"
    res = f_profile.resolve(msg)
    print(f"profile('other') = {res}")
    assert not res

    # Test 3: Help
    f_help = F.text.lower().in_({"сенсей помоги", "сенсей что умеешь?"})
    
    msg.text = "сенсей помоги"
    res = f_help.resolve(msg)
    print(f"help('сенсей помоги') = {res}")
    assert res
    
    msg.text = "other"
    res = f_help.resolve(msg)
    print(f"help('other') = {res}")
    assert not res

    print("All filters passed!")

if __name__ == "__main__":
    test_filters()
