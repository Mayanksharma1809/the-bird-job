

# ============================================================
# PORTFOLIO INTEGRATION — /candidate/ats/upload_portfolio
# ============================================================
@ats_bp.route('/candidate/ats/upload_portfolio', methods=['POST'])
def ats_upload_portfolio():
    try:
        user, _ = ensure_candidate_access()
        if not user: return jsonify({"error": "Unauthorized"}), 401
        res = request.files.get('resume')
        scr = request.form.get('ats_score')
        if not res: return jsonify({"error": "No file"}), 400
        existing = PortfolioItem.query.filter_by(candidate_user_id=user.id, item_type='resume').first()
        if not existing and len(user.portfolio_items) >= 5: return jsonify({"error": "Portfolio full"}), 400
        if existing: db.session.delete(existing)
        item = PortfolioItem(
            candidate_user_id=user.id,
            label=f"Resume (Score: {scr}%)",
            item_type='resume',
            file_name=res.filename,
            file_content=res.read(),
            content_type=res.content_type,
            ats_score=int(float(scr)) if scr else None
        )
        db.session.add(item)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Portfolio upload error: {e}")
        return jsonify({"error": str(e)}), 500
