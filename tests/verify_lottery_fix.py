import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import joinedload

from src.infra.database.models import Base, Ticket, User
from src.domain.repositories.ticket_repository import TicketRepository

async def main():
    # Setup in-memory DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    
    async with session_factory() as session:
        # Create user and tickets
        user = User(id=12345, username="test_user", first_name="Test")
        session.add(user)
        await session.flush()
        
        ticket1 = Ticket(user_id=user.id, code="ABC-1234-TEST")
        ticket2 = Ticket(user_id=user.id, code="XYZ-5678-TEST")
        session.add_all([ticket1, ticket2])
        await session.commit()
        
        # Test repository method
        repo = TicketRepository(session)
        print("Testing get_random_tickets_for_lottery...")
        
        try:
            tickets = await repo.get_random_tickets_for_lottery(1)
            print(f"Success! Got {len(tickets)} tickets.")
            for t in tickets:
                print(f"Ticket: {t.code}, User: {t.user.username}")
                
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
