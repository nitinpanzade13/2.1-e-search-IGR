import json
from app.core.database import SessionLocal
from app.models.location import District, Taluka, Village
from sqlalchemy import func

db = SessionLocal()

output = {}

# 1. duplicate District source_ids across districts
districts = db.query(District.source_id, func.count(District.id)).group_by(District.source_id).having(func.count(District.id) > 1).all()
output["duplicate_district_source_ids"] = [{"source_id": row[0], "count": row[1]} for row in districts]

# 2. duplicate Taluka source_ids across districts
talukas = db.query(Taluka.source_id, func.count(Taluka.id)).group_by(Taluka.source_id).having(func.count(Taluka.id) > 1).all()
output["duplicate_taluka_source_ids"] = [{"source_id": row[0], "count": row[1]} for row in talukas]

# 3. duplicate Village source_ids within relevant parent scopes (taluka_id)
villages = db.query(Village.taluka_id, Village.source_id, func.count(Village.id)).group_by(Village.taluka_id, Village.source_id).having(func.count(Village.id) > 1).all()
output["duplicate_village_source_ids_within_taluka"] = [{"taluka_id": str(row[0]), "source_id": row[1], "count": row[2]} for row in villages]

# 4. orphan Taluka rows (district_id is null or invalid)
invalid_districts_query = db.query(Taluka.id).filter(~Taluka.district_id.in_(db.query(District.id)))
output["orphan_talukas"] = invalid_districts_query.count()

# 5. orphan Village rows (taluka_id is null or invalid)
invalid_talukas_query = db.query(Village.id).filter(~Village.taluka_id.in_(db.query(Taluka.id)))
output["orphan_villages"] = invalid_talukas_query.count()

# Verify Kannad and Chopada
dist = db.query(District).filter(District.name_en == "छत्रपती संभाजीनगर").first()
tal_kannad = db.query(Taluka).filter(Taluka.name_en == "कन्नड", Taluka.district_id == dist.id).first()
vill_talner = db.query(Village).filter(Village.name_en == "तळनेर", Village.taluka_id == tal_kannad.id).first()

dist_jalgaon = db.query(District).filter(District.name_en == "जळगाव").first()
tal_chopada = db.query(Taluka).filter(Taluka.name_en == "चोपडा", Taluka.district_id == dist_jalgaon.id).first()

output["kannad"] = {
    "villages_count": db.query(Village).filter(Village.taluka_id == tal_kannad.id).count(),
    "has_talner": vill_talner is not None
}

output["chopada"] = {
    "villages_count": db.query(Village).filter(Village.taluka_id == tal_chopada.id).count(),
    "has_talner": db.query(Village).filter(Village.name_en == "तळनेर", Village.taluka_id == tal_chopada.id).first() is not None
}

with open("scratch/db_audit.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

