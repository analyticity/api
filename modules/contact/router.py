from fastapi import APIRouter, HTTPException

from modules.contact.schema import ContactRequest, ContactResponse
from modules.contact.service import send_contact_email
from core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("", response_model=ContactResponse)
def contact(request: ContactRequest) -> ContactResponse:
    try:
        send_contact_email(
            name=request.name,
            email=request.email,
            subject=request.subject,
            message=request.message,
        )
        return ContactResponse(success=True, message="Správa bola odoslaná.")
    except Exception as e:
        logger.error(f"Failed to send contact email: {e}")
        raise HTTPException(status_code=500, detail="Odoslanie správy zlyhalo.")
