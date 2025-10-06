import datetime
import json
import os
import tempfile
#from flask import request, redirect, url_for, render_template, make_response, jsonify
from flask import request, redirect, url_for, render_template, make_response, jsonify, session

from lpg import app, db
from lpg.DB.model import User, Document, Statistic, GapAnalysisResult
from lpg.controller.auth import generate_jwt, verify_jwt
from lpg.controller.document import upload_to_s3, download_parse_clean, extract_pdf, compare_documents_with_openai
from lpg.controller.generate import generate_similar_content
from lpg.log import logger
from lpg.utils import generate_random_string
from lpg.s3_utils import upload_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@app.route('/')
@app.route('/signin', methods=['POST', 'GET'])
def signin():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            logger.info("User authenticated successfully")
            jwt_token = generate_jwt(user.id)
            response = redirect(url_for('dashboard'))
            response.set_cookie('token', str(jwt_token))
            return response
        else:
            logger.error('Invalid username or password')
    return render_template('signin.html')


@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()
        if user:
            logger.info("User Created successfully")
            jwt_token = generate_jwt(str(user.id))
            response = redirect(url_for('dashboard'))
            response.set_cookie('token', str(jwt_token), httponly=True, secure=True, samesite='Lax')
            return response
        else:
            logger.error('Invalid username or password')
    return render_template('signup.html')


@app.route('/upload', methods=['POST', 'GET'])
def upload():
    user_id = verify_jwt(request.cookies.get('token'))
    if not user_id:
        return redirect(url_for('signin'))
    if request.method == 'POST':
        doc_name = request.form['doc_name']
        description = request.form['description']
        file = request.files['file']
        user_id = verify_jwt(request.cookies.get('token'))
        if not user_id:
            return redirect(url_for('signin'))
        logger.info(f" The user id from token is {user_id}")
        unique_filename = f"{doc_name}_{datetime.datetime.now(datetime.UTC).strftime('%Y%m%d%H%M%S%f')}"
        logger.info(unique_filename)
        try:
            s3_file_url = upload_to_s3(file, os.getenv("AWS_S3_BUCKET"), unique_filename)
            if s3_file_url:
                document = Document(name=doc_name, description=description, file_url=s3_file_url, user_id=user_id)
                db.session.add(document)
                db.session.commit()
                #documents = Document.query.all()
                documents = Document.query.filter_by(user_id=user_id).all()
                return render_template('dashboard.html', documents=documents, selected_document=None,
                                       word_count=0, sentiment='N/A', asset="N/A", tags="N/A")
            else:
                logger.error("S3 upload failed - upload_to_s3 returned None")
                return render_template('upload.html', error="Failed to upload file to S3. Please check your AWS credentials and try again.")
        except Exception as e:
            logger.error(f"Error Uploading file into S3{e}")
            return render_template('upload.html', error=f"Upload failed: {str(e)}")
    return render_template('upload.html')


@app.route('/documents')
def my_documents():
    user_id = verify_jwt(request.cookies.get('token'))
    if not user_id:
        return redirect(url_for('signin'))
    documents = Document.query.filter_by(user_id=user_id).all()
    return render_template('documents.html', documents=documents)


# # @app.route('/')
@app.route('/index')
def index():
    return render_template('index.html')


@app.route('/dashboard', methods=['POST', 'GET'])
def dashboard():
    word_count = 0
    tags = 'N/A'
    sentiment = 'N/A'
    asset = 'N/A'

    # Verify user authentication
    user_id = verify_jwt(request.cookies.get('token'))
    if not user_id:
        return redirect(url_for('signin'))

    # Retrieve documents for the authenticated user
    documents = Document.query.filter_by(user_id=user_id).all()

    # Handle AJAX POST requests
    if request.method == 'POST':
        # Check if the request is an AJAX call
        if request.is_json:
            data = request.get_json()
            action = data.get("action")
            selected_document = data.get("document")
            document = Document.query.filter(Document.name == selected_document).with_entities(
                Document.file_url, Document.id, Document.local).first()
            document_stat = Statistic.query.filter(Statistic.document_id == document.id).first()
            if action == "analyze":
                if document:
                    if document_stat:
                        return jsonify({
                            "word_count": document_stat.word_count,
                            "tags": document_stat.tags,
                            "sentiment": document_stat.sentiment,
                            "asset": document_stat.asset
                        })
                    else:
                        assets, sentiment, tags, word_count, local = download_parse_clean(
                            asset, document.file_url, sentiment, tags, word_count
                        )
                        # Save the statistics to the database
                        db.session.query(Document).filter(Document.id == document.id).update({Document.local: local})
                        db.session.flush()
                        statistic = Statistic(
                            word_count=word_count,
                            tags=json.dumps(tags),
                            sentiment=sentiment,
                            asset=asset,
                            document_id=document.id
                        )
                        db.session.add(statistic)
                        db.session.commit()
                        return jsonify({
                            "word_count": word_count,
                            "tags": json.loads(document_stat.tags),
                            "sentiment": sentiment,
                            "asset": asset
                        })
                else:
                    return jsonify({"error": "Document not found."}), 404
            elif action == "generate":
                if document:
                    if document_stat:
                        pdf_name = document.local
                        word_count = document_stat.word_count
                        tags = str(document_stat.tags)
                        sentiment = document_stat.sentiment
                        asset = document_stat.asset
                        new_file_name = f"{generate_random_string()}.pdf"
                        generate_similar_content(pdf_name=pdf_name, word_count=word_count, tags=tags,
                                                 sentiment=sentiment, asset=asset,
                                                 new_file_name=new_file_name)
                        return jsonify({"message": "Similar document generated successfully!"})
                    else:
                        assets, sentiment, tags, word_count, local = download_parse_clean(
                            asset, document.file_url, sentiment, tags, word_count
                        )
                        # Save the statistics to the database
                        document.local = local
                        statistic = Statistic(
                            word_count=word_count,
                            tags=json.dumps(tags),
                            sentiment=sentiment,
                            asset=asset,
                            document_id=document.id
                        )
                        db.session.add(document)
                        db.session.add(statistic)
                        db.session.commit()
                        return jsonify({
                            "word_count": word_count,
                            "tags": tags,
                            "sentiment": sentiment,
                            "asset": asset
                        })
                else:
                    return jsonify({"error": "Document not found."}), 404
            return jsonify({"error": "Invalid action."}), 400

    # Handle standard GET requests
    return render_template(
        'dashboard.html',
        documents=documents,
        selected_document=None,
        word_count=word_count,
        sentiment=sentiment,
        asset=asset,
        tags=tags
    )


@app.route('/set_selected_document', methods=['POST'])
def set_selected_document():
    document_ids = request.form.getlist('document_ids')
    session['selected_document_ids'] = document_ids
    return redirect(url_for('verify_gap'))


@app.route('/verify_gap', methods=['GET'])
def verify_gap():
    user_id = verify_jwt(request.cookies.get('token'))
    if not user_id:
        return redirect(url_for('signin'))
    documents = Document.query.filter_by(user_id=user_id).all()
    selected_document_ids = session.get('selected_document_ids', [])
    selected_documents = []
    if selected_document_ids:
        selected_documents = Document.query.filter(Document.id.in_(selected_document_ids)).all()
    return render_template('verify_gap.html', documents=documents, selected_documents=selected_documents, selected_document_ids=selected_document_ids)


# Analyze Gap 
@app.route('/analyze_gap', methods=['POST'])
def analyze_gap():
    user_id = verify_jwt(request.cookies.get('token'))
    if not user_id:
        return redirect(url_for('signin'))

    selected_document_ids = session.get('selected_document_ids', [])
    if len(selected_document_ids) < 2:
        gap_results = ["⚠️ **ERROR**", "Select at least two documents to perform gap analysis."]
        return render_template('verify_gap.html', gap_results=gap_results)

    docs = Document.query.filter(Document.id.in_(selected_document_ids)).all()
    if len(docs) < 2:
        gap_results = ["⚠️ **ERROR**", "Not enough documents found."]
        return render_template('verify_gap.html', gap_results=gap_results)

    import boto3
    texts = []
    temp_files = []
    pdf_s3_url = None
    try:
        for doc in docs:
            s3 = boto3.client('s3')
            bucket_name = os.getenv("AWS_S3_BUCKET")
            base_url = f'https://{bucket_name}.s3.us-east-2.amazonaws.com/'
            s3_key = doc.file_url.replace(base_url, '')
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file_path = temp_file.name
            temp_file.close()
            s3.download_file(bucket_name, s3_key, temp_file_path)
            text = extract_pdf(temp_file_path)
            texts.append(text)
            temp_files.append(temp_file_path)

        gap_results = []
        n = len(docs)
        gap_results.append(f"Analyzing {n} documents for gaps and recommendations...")
        gap_results.append("")
        for i in range(n):
            for j in range(i+1, n):
                gap_results.append(f"🔍 COMPARISON: {docs[i].name} vs {docs[j].name}")
                comparison = compare_documents_with_openai(texts[i], texts[j], docs[i].name, docs[j].name)
                lines = comparison.split('\n')
                for line in lines:
                    line = line.strip()
                    if line:
                        if line.startswith('**') and line.endswith('**'):
                            gap_results.append(line)
                        elif line.startswith('- '):
                            gap_results.append(line)
                        else:
                            gap_results.append(line)
                gap_results.append("")

        s3_upload_error = None
        if gap_results and not (gap_results[0].startswith('❌') or gap_results[0].startswith('⚠️')):
            try:
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                from reportlab.lib import colors
                from reportlab.lib.enums import TA_CENTER, TA_LEFT

                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as pdf_temp:
                    pdf_path = pdf_temp.name
                doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
                story = []
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    'CustomTitle', parent=styles['Heading1'], fontSize=24, spaceAfter=30, alignment=TA_CENTER, textColor=colors.darkblue)
                heading_style = ParagraphStyle(
                    'CustomHeading', parent=styles['Heading2'], fontSize=16, spaceAfter=12, spaceBefore=20, textColor=colors.darkblue)
                normal_style = ParagraphStyle(
                    'CustomNormal', parent=styles['Normal'], fontSize=11, spaceAfter=6, alignment=TA_LEFT)
                bullet_style = ParagraphStyle(
                    'CustomBullet', parent=styles['Normal'], fontSize=11, spaceAfter=6, leftIndent=20, alignment=TA_LEFT)
                table_header_style = ParagraphStyle(
                    'TableHeader', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER, textColor=colors.whitesmoke, backColor=colors.grey)
                # Add title
                story.append(Paragraph("Gap Analysis Report", title_style))
                story.append(Spacer(1, 20))
                from datetime import datetime
                story.append(Paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", normal_style))
                story.append(Spacer(1, 20))
                story.append(Paragraph("Documents Analyzed:", heading_style))
                for doc_item in docs:
                    story.append(Paragraph(f"• {doc_item.name}", bullet_style))
                story.append(Spacer(1, 20))
                # --- Improved Markdown Table Parsing ---
                current_section = None
                table_data = []
                in_table = False
                for idx, line in enumerate(gap_results):
                    line = line.strip()
                    if not line:
                        continue
                    # Section headers
                    if line.startswith('🔍 COMPARISON:'):
                        story.append(Paragraph(line, heading_style))
                        continue
                    if line.startswith('**') and line.endswith('**'):
                        clean_line = line.replace('**', '')
                        story.append(Paragraph(clean_line, heading_style))
                        continue
                    if line.startswith('- '):
                        story.append(Paragraph(line, bullet_style))
                        continue
                    # Table detection
                    if line.startswith('|') and line.count('|') > 2:
                        # Skip markdown separator lines
                        if set(line.replace('|', '').replace(' ', '')) <= set('-:'):
                            continue
                        # Split and clean cells
                        cells = [cell.strip() for cell in line.split('|')[1:-1]]
                        # Use Paragraph for each cell for wrapping
                        if not in_table:
                            table_data = []
                            in_table = True
                        table_data.append([Paragraph(cell, normal_style) for cell in cells])
                        continue
                    # If we were building a table and hit a non-table line, add the table
                    if in_table and (not line.startswith('|') or idx == len(gap_results)-1):
                        if len(table_data) > 1:
                            # Set column widths (auto for 2/3 columns, else equal)
                            col_count = len(table_data[0])
                            if col_count == 2:
                                col_widths = [2.5*inch, 3.5*inch]
                            elif col_count == 3:
                                col_widths = [2*inch, 2.5*inch, 1.5*inch]
                            else:
                                col_widths = [None]*col_count
                            table = Table(table_data, colWidths=col_widths)
                            table.setStyle(TableStyle([
                                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                                ('FONTSIZE', (0, 0), (-1, 0), 12),
                                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                                ('FONTSIZE', (0, 1), (-1, -1), 10),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ]))
                            story.append(table)
                            story.append(Spacer(1, 12))
                        table_data = []
                        in_table = False
                    # Section headers
                    if line.startswith('📌') or line.startswith('✅') or line.startswith('❌'):
                        story.append(Paragraph(line, heading_style))
                        continue
                    # Regular text
                    if not line.startswith('|'):
                        story.append(Paragraph(line, normal_style))
                # Handle any remaining table at the end
                if in_table and len(table_data) > 1:
                    col_count = len(table_data[0])
                    if col_count == 2:
                        col_widths = [2.5*inch, 3.5*inch]
                    elif col_count == 3:
                        col_widths = [2*inch, 2.5*inch, 1.5*inch]
                    else:
                        col_widths = [None]*col_count
                    table = Table(table_data, colWidths=col_widths)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 12),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ]))
                    story.append(table)
                    story.append(Spacer(1, 12))
                doc.build(story)
                # S3 upload and rest of code unchanged...
                # Get the directory of the first document to store the gap analysis in the same location
                first_doc_s3_key = docs[0].file_url.replace(f'https://{bucket_name}.s3.us-east-2.amazonaws.com/', '')
                doc_directory = '/'.join(first_doc_s3_key.split('/')[:-1])  # Remove filename, keep directory
                # Create gap analysis filename with timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                gap_analysis_filename = f"gap_analysis_{timestamp}.pdf"
                # Upload PDF to S3 in the same directory as the source documents
                if doc_directory:
                    s3_key = f"{doc_directory}/{gap_analysis_filename}"
                else:
                    s3_key = gap_analysis_filename
                try:
                    upload_file(pdf_path, s3_key)
                    pdf_s3_url = f"https://{bucket_name}.s3.us-east-2.amazonaws.com/{s3_key}"
                    # Store in DB
                    gap_result_entry = GapAnalysisResult(
                        user_id=user_id,
                        document_ids=','.join([str(doc.id) for doc in docs]),
                        result='\n'.join(gap_results),
                        pdf_s3_url=pdf_s3_url
                    )
                    db.session.add(gap_result_entry)
                    db.session.commit()
                except Exception as upload_error:
                    logger.error(f"S3 upload failed: {upload_error}")
                    pdf_s3_url = None
                    s3_upload_error = "Gap analysis PDF could not be uploaded to S3."
            except Exception as pdf_error:
                logger.error(f"Error generating PDF: {pdf_error}")
                pdf_s3_url = None
                s3_upload_error = "Gap analysis PDF could not be generated."
    except Exception as e:
        logger.error(f"Error during gap analysis: {e}")
        gap_results = ["❌ **ERROR**", f"An error occurred during analysis: {str(e)}"]
    finally:
        for temp_file_path in temp_files:
            try:
                os.remove(temp_file_path)
            except OSError as e:
                logger.warning(f"Could not remove temporary file {temp_file_path}: {e}")
        if 'pdf_path' in locals():
            try:
                os.remove(pdf_path)
            except Exception:
                pass
    return render_template('verify_gap.html', gap_results=gap_results, documents=docs, selected_documents=docs, selected_document_ids=selected_document_ids, pdf_s3_url=pdf_s3_url, s3_upload_error=s3_upload_error)


@app.route('/logout', methods=['GET'])
def logout():
    response = make_response(redirect(url_for('signin')))
    response.delete_cookie('token')
    return response
