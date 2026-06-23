from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.question import Question
from app.schemas.question import QuestionCreate, QuestionUpdate, QuestionResponse
from app.auth.jwt_handler import get_current_user

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=List[QuestionResponse])
def get_questions(
    interview_type: Optional[str] = None,
    track: Optional[str] = None,
    difficulty: Optional[str] = None,
    db: Session = Depends(get_db),
    _: int = Depends(get_current_user),
):
    q = db.query(Question)
    if interview_type:
        q = q.filter(Question.interview_type == interview_type)
    if track:
        q = q.filter(Question.track == track)
    if difficulty:
        q = q.filter(Question.difficulty == difficulty)
    return q.order_by(Question.id).all()


@router.post("", response_model=QuestionResponse, status_code=201)
def create_question(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    _: int = Depends(get_current_user),
):
    question = Question(**data.model_dump())
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    data: QuestionUpdate,
    db: Session = Depends(get_db),
    _: int = Depends(get_current_user),
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    _: int = Depends(get_current_user),
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    db.delete(question)
    db.commit()
    return {"message": "Question deleted"}
