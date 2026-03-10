from core.databases import SessionLocal
from services.messaging_service import MessagingService

db = SessionLocal()
try:
    convos = MessagingService.get_unified_conversations("3f091b25-f72c-49ff-b28f-13b4faceb308", db)
    for c in convos[:5]:
        print(f"[{c['type']}] {c['name']}: unread={c['unread_count']}, last={c.get('last_message_at','none')}")
    total = MessagingService.get_total_unread_count("3f091b25-f72c-49ff-b28f-13b4faceb308", db)
    print(f"Total unread: {total}")
finally:
    db.close()
