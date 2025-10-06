import datetime

from sqlalchemy import Column, INTEGER, String, DateTime, ForeignKey, TEXT

from lpg import db


class User(db.Model):
    __tablename__ = "users"
    id = Column(INTEGER, primary_key=True, nullable=False, autoincrement=True, unique=True)
    username = Column(String(50), nullable=False, )
    password = Column(String(50), nullable=False)

    def __init__(self, username=None, password=None):
        self.username = username
        self.password = password

    def __repr__(self):
        return f"{self.__class__.__name__}(name = {self.username})"

    def __str__(self):
        return self.username


class Document(db.Model):
    __tablename__ = "documents"
    id = Column(INTEGER, primary_key=True, nullable=False, autoincrement=True, unique=True)
    name = Column(String(500), nullable=False, )
    description = Column(String(500), nullable=False)
    file_url = Column(String(500), nullable=False)
    upload_date = Column(DateTime, nullable=False, default=datetime.datetime.now(),
                         onupdate=datetime.datetime.now())
    user_id = Column(INTEGER, ForeignKey("users.id"), nullable=False)
    local = Column(String(500), nullable=True)

    def __init__(self, name=None, description=None, file_url=None, upload_date=None, user_id=None, local=None):
        self.name = name
        self.description = description
        self.file_url = file_url
        self.upload_date = upload_date
        self.user_id = user_id
        self.local = local

    def __repr__(self):
        return f"{self.__class__.__name__}(name = {self.name})"

    def __str__(self):
        return self.name


class Statistic(db.Model):
    __tablename__ = "statistics"
    id = Column(INTEGER, primary_key=True, nullable=False, autoincrement=True, unique=True)
    word_count = Column(INTEGER, nullable=False, default=0)
    tags = Column(TEXT, nullable=False, default="")
    sentiment = Column(String(500), nullable=False, default="")
    asset = Column(TEXT, nullable=False, default="")
    document_id = Column(INTEGER, ForeignKey("documents.id"), nullable=False)

    def __init__(self, word_count, tags, sentiment, asset, document_id):
        self.word_count = word_count
        self.tags = tags
        self.sentiment = sentiment
        self.asset = asset
        self.document_id = document_id

    def __repr__(self):
        return f"{self.__class__.__name__}(id = {self.id})"

    def __str__(self):
        return self.id


class GapAnalysisResult(db.Model):
    __tablename__ = "gap_analysis_results"
    id = Column(INTEGER, primary_key=True, nullable=False, autoincrement=True, unique=True)
    user_id = Column(INTEGER, ForeignKey("users.id"), nullable=False)
    document_ids = Column(String(255), nullable=False)  # Comma-separated document IDs
    result = Column(TEXT, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now)
    pdf_s3_url = Column(String(500), nullable=True)  # S3 URL for the generated PDF

    def __init__(self, user_id, document_ids, result, created_at=None, pdf_s3_url=None):
        self.user_id = user_id
        self.document_ids = document_ids
        self.result = result
        self.created_at = created_at or datetime.datetime.now()
        self.pdf_s3_url = pdf_s3_url

    def __repr__(self):
        return f"{self.__class__.__name__}(id = {self.id}, user_id = {self.user_id})"

    def __str__(self):
        return str(self.id)
