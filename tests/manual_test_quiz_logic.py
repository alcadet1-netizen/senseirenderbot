
import asyncio
import json

async def test_quiz_logic():
    print("Testing Quiz Logic...")
    
    # Simulate DB/State data
    # Case 1: Single answer
    db_answer_1 = "apple"
    state_answer_1 = db_answer_1.lower().strip()
    
    # Case 2: Multiple answers
    db_answer_2 = "apple | pear | banana"
    state_answer_2 = db_answer_2.lower().strip()
    
    # Logic from check_answer
    def check(state_ans, user_input):
        correct_variants = [v.strip() for v in state_ans.split("|")]
        user_answer = user_input.lower().strip()
        return user_answer in correct_variants

    # Tests
    assert check(state_answer_1, "apple") == True
    assert check(state_answer_1, "Apple") == True
    assert check(state_answer_1, "pear") == False
    
    assert check(state_answer_2, "apple") == True
    assert check(state_answer_2, "PEAR") == True
    assert check(state_answer_2, " banana ") == True
    assert check(state_answer_2, "orange") == False
    
    print("All logic tests passed!")

if __name__ == "__main__":
    asyncio.run(test_quiz_logic())
