# app/services/cleanup_service.py
from datetime import datetime, timedelta
from app.services.social_posts_service import SocialPostService


async def cleanup_expired_posts(db):
    """
    Xóa vĩnh viễn các bài viết đã bị xóa tạm thời quá 10 ngày
    """
    try:
        service = SocialPostService(db)
        deleted_count = await service.permanently_delete_expired_posts()
        return deleted_count
    except Exception as e:
        print(f"Lỗi trong cleanup_expired_posts: {e}")
        return 0


async def cleanup_expired_notifications(db):
    """
    Xóa thông báo cũ hơn 30 ngày
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        collection = db["notifications"]
        result = await collection.delete_many({
            "created_at": {"$lt": cutoff_date},
            "is_read": True
        })
        return result.deleted_count
    except Exception as e:
        print(f"Lỗi trong cleanup_expired_notifications: {e}")
        return 0