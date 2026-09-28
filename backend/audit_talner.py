from app.core.database import SessionLocal
from app.models.location import State, District, Taluka, Village
import sys
import json

def audit():
    db = SessionLocal()
    try:
        # 1. Look for District: छत्रपती संभाजीनगर
        districts = db.query(District).all()
        
        districts = db.query(District).all()
        
        print("--- ALL DISTRICTS ---")
        dist = None
        for d in districts:
            if "संभाजी" in str(d.name_en) or "संभाजी" in str(d.name_mr):
                dist = d
            
        if not dist:
            print("District not found!")
            return
        
        talukas = db.query(Taluka).filter(Taluka.district_id == dist.id).all()
        
        print("\n--- ALL TALUKAS FOR DISTRICT ---")
        for t in talukas:
            print(f"ID: {t.id} | SourceID: {t.source_id} | Name EN: {t.name_en} | Name MR: {t.name_mr} | DistID: {t.district_id}")
            
        taluka = next((t for t in talukas if "कन्नड" in str(t.name_mr) or "कन्नड" in str(t.name_en)), None)
        if not taluka:
            print("Specific taluka Kannad not found!")
            return
        
        # 3. Look for Village: तळनेर / Talner in this taluka
        villages_search = db.query(Village).filter(
            (Village.name_en.ilike("%talner%")) |
            (Village.name_mr.ilike("%तळनेर%")) |
            (Village.name_en.ilike("%talane%"))
        ).all()
        
        print("\n--- 'तळनेर' / 'Talner' VILLAGES IN DB ---")
        for v in villages_search:
            print(f"ID: {v.id} | SourceID: {v.source_id} | Name EN: {v.name_en} | Name MR: {v.name_mr} | TalukaID: {v.taluka_id}")
            
        # 4. Get ALL villages for this taluka
        all_villages = db.query(Village).filter(Village.taluka_id == taluka.id).all()
        
        print(f"\n--- ALL VILLAGES FOR {taluka.name_mr or taluka.name_en} ({taluka.source_id}) ---")
        print(f"Total villages: {len(all_villages)}")
        
        valid_source = sum(1 for v in all_villages if v.source_id)
        valid_taluka = sum(1 for v in all_villages if v.taluka_id)
        non_empty_names = sum(1 for v in all_villages if v.name_mr or v.name_en)
        
        from collections import Counter
        source_ids = [v.source_id for v in all_villages if v.source_id]
        dupe_sources = sum(1 for k, count in Counter(source_ids).items() if count > 1)
        
        print(f"Valid source_id: {valid_source}")
        print(f"Valid taluka_id: {valid_taluka}")
        print(f"Non-empty names: {non_empty_names}")
        report_path = "c:/Users/nitin/OneDrive/Documents/VIIT/4th Year/Internship/2.1 e-search IGR/scratch/village_data_audit_talner.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("# Village Data Audit: तळनेर (Talner)\n\n")
            
            f.write("### A. Database\n")
            if not villages_search:
                f.write("- Does 'तळनेर' exist? **No**\n")
                f.write("- Exact database row: N/A\n")
            else:
                f.write("- Does 'तळनेर' exist? **Yes**\n")
                for v in villages_search:
                    f.write(f"- Exact database row: ID: {v.id}, SourceID: {v.source_id}, Code: {getattr(v, 'village_code', 'N/A')}\n")
                    f.write(f"- District relationship: {v.district_id if hasattr(v, 'district_id') else 'N/A'}\n")
                    f.write(f"- Taluka relationship: {v.taluka_id}\n")
            
            f.write("\n### B. Taluka completeness\n")
            f.write(f"- Total villages in {taluka.name_mr or taluka.name_en} (Source ID {taluka.source_id}): {len(all_villages)}\n")
            f.write(f"- Valid source_id: {valid_source}\n")
            f.write(f"- Valid taluka_id: {valid_taluka}\n")
            f.write(f"- Non-empty names: {non_empty_names}\n")
            f.write(f"- Duplicate source_ids: {dupe_sources}\n")
            
            f.write("\nVillage List:\n")
            f.write("```text\nsource_id | name_en | name_mr | taluka\n")
            for v in all_villages:
                f.write(f"{v.source_id} | {v.name_en} | {v.name_mr} | {v.taluka_id}\n")
            f.write("```\n")
            
        print(f"Report written to {report_path}")
            
    finally:
        db.close()

if __name__ == "__main__":
    audit()
