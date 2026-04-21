# app/api/v1/endpoints/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError
import boto3
import uuid
from app.core.r2_config import R2Config
from app.core.security import get_current_user

router = APIRouter(prefix="/upload", tags=["Upload"])

def get_r2_client():
    """Khởi tạo S3 client cho R2"""
    # Kiểm tra config trước
    if not R2Config.ACCESS_KEY_ID or not R2Config.SECRET_ACCESS_KEY:
        raise ValueError("R2 credentials not configured! Check .env file")
    
    return boto3.client(
        "s3",
        endpoint_url=R2Config.ENDPOINT_URL,
        aws_access_key_id=R2Config.ACCESS_KEY_ID,
        aws_secret_access_key=R2Config.SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto"
    )

@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """
    Upload ảnh lên Cloudflare R2
    Trả về URL công khai của ảnh
    """
    # Kiểm tra file có phải ảnh không
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File không phải là ảnh")
    
    # Kiểm tra kích thước file (tối đa 10MB)
    MAX_SIZE = 10 * 1024 * 1024
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail=f"File quá lớn. Tối đa {MAX_SIZE // (1024*1024)}MB")
    
    try:
        # Tạo tên file unique
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ["jpg", "jpeg", "png", "gif", "webp", "avif"]:
            raise HTTPException(status_code=400, detail="Định dạng ảnh không được hỗ trợ")
        
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Upload lên R2
        s3 = get_r2_client()
        
        print(f"Uploading to bucket: {R2Config.BUCKET_NAME}")
        print(f"Filename: {unique_filename}")
        
        s3.put_object(
            Bucket=R2Config.BUCKET_NAME,
            Key=unique_filename,
            Body=content,
            ContentType=file.content_type,
            CacheControl="public, max-age=31536000"
        )
        
        # Tạo URL công khai
        public_url = f"{R2Config.PUBLIC_URL_BASE}/{unique_filename}"
        
        print(f"Upload successful! URL: {public_url}")
        
        return {
            "success": True,
            "image_url": public_url,
            "filename": unique_filename,
            "size": len(content)
        }
        
    except NoCredentialsError as e:
        print(f"Credentials error: {str(e)}")
        raise HTTPException(status_code=500, detail="Lỗi xác thực với Cloudflare R2. Kiểm tra lại Access Key và Secret Key.")
    except ClientError as e:
        print(f"AWS Client error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi từ Cloudflare R2: {str(e)}")
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi khi upload ảnh: {str(e)}")