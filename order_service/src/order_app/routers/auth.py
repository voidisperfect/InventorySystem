from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from ..auth import create_access_token

router = APIRouter(tags=["Authentication"])

@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Generates a token with both 'sub' and 'user_id' to avoid key mismatch
    access_token = create_access_token(
        data={"sub": form_data.username, "user_id": form_data.username, "email": f"{form_data.username}@example.com"}
    )
    return {"access_token": access_token, "token_type": "bearer"}
