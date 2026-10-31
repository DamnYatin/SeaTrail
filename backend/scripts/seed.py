"""
SealTrail Synthetic Data Seeder.
Populates realistic forensic investigation cases, evidence items, chain-of-custody transfers,
dual-authorization approval queues, people, events, notes, and defensible audit trails.
All seeded data is synthetic and generated programmatically through the real service layer.
"""

import io
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text

from app.config import settings
from app.db import Base, get_db_session, set_engine
from app.models.approvals import ApprovalKind, ApprovalRequest, ApprovalStatus
from app.models.cases import Case, CaseClassification, CaseMember, CaseMemberRole, CaseStatus
from app.models.custody import CustodyTransfer, TransferStatus
from app.models.evidence import EvidenceItem, EvidenceStatus, EvidenceType
from app.models.links import (
    Annotation,
    CaseEvent,
    CaseNote,
    EvidenceLink,
    LinkTargetType,
    Person,
    PersonRole,
)
from app.models.users import User, UserRole
from app.security.passwords import hash_password
from app.services import (
    anomaly,
    audit_chain,
    checkpoints,
    intake,
    retention,
    storage,
)
from app.services.audit_chain import AuditAction, append


def create_synthetic_png() -> bytes:
    """Generate a minimal valid 1x1 PNG image."""
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00"
        b"\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfeA\x0c\x8f"
        b"\x96\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def seed_database():
    print("=" * 60)
    print("  SEALTRAIL SYNTHETIC FORENSIC DATA SEEDER")
    print("=" * 60)

    # Verify primary database connection; fallback to local SQLite if unreachable
    try:
        with get_db_session() as test_session:
            test_session.execute(text("SELECT 1"))
    except Exception:
        db_path = str(backend_dir / "sealtrail.db")
        print(f"[INFO] Primary database unreachable. Initializing local database: {db_path}")
        sqlite_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sqlite_engine)
        set_engine(sqlite_engine)
        storage.set_mock_storage(True)

    # Check S3 connectivity once upfront
    try:
        s3 = storage.get_s3_client()
        if s3:
            s3.list_buckets()
    except Exception:
        storage.set_mock_storage(True)

    with get_db_session() as session:
        # Check if already seeded
        existing_cases = session.query(Case).count()
        if existing_cases > 0:
            print("[INFO] Database already contains cases. Skipping seeding.")
            return

        # Ensure genesis audit entry exists
        audit_chain.ensure_genesis_entry(session)

        # 1. Seed Users
        print("[1/6] Creating authorized personnel...")
        domain = settings.SEED_EMAIL_DOMAIN
        pwd_hash = hash_password(settings.SEED_PASSWORD)

        users_data = [
            ("admin", f"admin@{domain}", "Ananya Sharma", UserRole.ADMIN),
            ("sup1", f"supervisor1@{domain}", "Vikramaditya Rathore", UserRole.SUPERVISOR),
            ("sup2", f"supervisor2@{domain}", "Meera Nambiar", UserRole.SUPERVISOR),
            ("inv1", f"investigator1@{domain}", "Karan Verma", UserRole.INVESTIGATOR),
            ("inv2", f"investigator2@{domain}", "Priya Deshmukh", UserRole.INVESTIGATOR),
            ("cust1", f"custodian1@{domain}", "Rajesh Kulkarni", UserRole.CUSTODIAN),
            ("aud1", f"auditor1@{domain}", "Sunita Rao", UserRole.AUDITOR),
        ]

        users: dict[str, User] = {}
        for key, email, name, role in users_data:
            u = User(
                email=email,
                full_name=name,
                role=role,
                password_hash=pwd_hash,
                is_active=True,
            )
            session.add(u)
            users[key] = u

        session.flush()

        for key, u in users.items():
            append(
                session=session,
                actor=users["admin"],
                action=AuditAction.USER_CREATED,
                payload={
                    "user_id": u.id,
                    "email": u.email,
                    "role": u.role.value,
                    "full_name": u.full_name,
                },
            )

        # 2. Retention Policies
        print("[2/6] Seeding statutory retention policies...")
        policies = retention.ensure_default_policies(session)
        standard_policy = policies[0]
        extended_policy = policies[1]
        short_policy = policies[2]

        # 3. Create Cases
        print("[3/6] Creating active forensic case workspaces...")
        c1 = Case(
            case_number="SL26-0042",
            name="Operation Falcon: UPI Mule Account & SIM Swapping Syndicate",
            description="Coordinated cyber financial crime involving synthetic bank accounts and illicit payment gateways.",
            status=CaseStatus.OPEN,
            classification=CaseClassification.RESTRICTED,
            lead_user_id=users["inv1"].id,
            retention_policy_id=standard_policy.id,
            created_by=users["sup1"].id,
        )
        c2 = Case(
            case_number="SL26-0078",
            name="Project Silk: Textile Exporter Proprietary IP Exfiltration",
            description="Investigation into unauthorized extraction and cloud exfiltration of digital weave patterns and supplier databases.",
            status=CaseStatus.OPEN,
            classification=CaseClassification.CONFIDENTIAL,
            lead_user_id=users["inv2"].id,
            retention_policy_id=extended_policy.id,
            created_by=users["sup1"].id,
        )
        c3 = Case(
            case_number="SL26-0105",
            name="Incident RedPulse: District General Hospital Ransomware Intrusion",
            description="Akira ransomware deployment targeting emergency health records infrastructure and patient care telemetries.",
            status=CaseStatus.OPEN,
            classification=CaseClassification.RESTRICTED,
            lead_user_id=users["inv1"].id,
            retention_policy_id=short_policy.id,
            created_by=users["sup2"].id,
        )
        session.add_all([c1, c2, c3])
        session.flush()

        for c, creator in [(c1, users["sup1"]), (c2, users["sup1"]), (c3, users["sup2"])]:
            append(
                session=session,
                actor=creator,
                action=AuditAction.CASE_CREATED,
                case_id=c.id,
                payload={
                    "case_number": c.case_number,
                    "name": c.name,
                    "classification": c.classification.value,
                },
            )

        # Case Members
        members_data = [
            (c1, users["inv1"], CaseMemberRole.LEAD),
            (c1, users["inv2"], CaseMemberRole.MEMBER),
            (c1, users["sup1"], CaseMemberRole.MEMBER),
            (c1, users["cust1"], CaseMemberRole.MEMBER),
            (c2, users["inv2"], CaseMemberRole.LEAD),
            (c2, users["sup1"], CaseMemberRole.MEMBER),
            (c2, users["cust1"], CaseMemberRole.MEMBER),
            (c3, users["inv1"], CaseMemberRole.LEAD),
            (c3, users["sup2"], CaseMemberRole.MEMBER),
            (c3, users["cust1"], CaseMemberRole.MEMBER),
        ]
        for c, u, role in members_data:
            cm = CaseMember(case_id=c.id, user_id=u.id, case_role=role, added_by=c.created_by)
            session.add(cm)
            append(
                session=session,
                actor=users["sup1"],
                action=AuditAction.CASE_MEMBER_ADDED,
                case_id=c.id,
                payload={"user_id": u.id, "case_role": role.value},
            )
        session.flush()

        # People, Events, Notes
        print("[4/6] Linking entities: persons of interest, events, and case notes...")
        # People
        p1 = Person(
            case_id=c1.id,
            full_name="Rohan K. Mehta",
            role_in_case=PersonRole.SUSPECT,
            contact="+91 98201 54321",
            notes="Mule account aggregator operating out of Surat",
            created_by=users["inv1"].id,
        )
        p2 = Person(
            case_id=c1.id,
            full_name="Arun Patel",
            role_in_case=PersonRole.VICTIM,
            contact="+91 94250 11223",
            notes="Reported unauthorized withdrawals of Rs. 4,80,000",
            created_by=users["inv1"].id,
        )
        p3 = Person(
            case_id=c2.id,
            full_name="Gaurav Sen",
            role_in_case=PersonRole.SUSPECT,
            contact="gaurav.s@extextile.com",
            notes="Former senior CAD designer terminated for compliance breach",
            created_by=users["inv2"].id,
        )
        p4 = Person(
            case_id=c3.id,
            full_name="Dr. Sanjay Bhatia",
            role_in_case=PersonRole.WITNESS,
            contact="sbhatia@district-med.org",
            notes="Chief Medical Information Officer",
            created_by=users["inv1"].id,
        )
        session.add_all([p1, p2, p3, p4])
        session.flush()

        for p in [p1, p2, p3, p4]:
            append(
                session=session,
                actor=users["inv1"],
                action=AuditAction.PERSON_ADDED,
                case_id=p.case_id,
                payload={"person_id": p.id, "name": p.full_name, "role": p.role_in_case.value},
            )

        # Events
        ev1 = CaseEvent(
            case_id=c1.id,
            title="SIM Swap at Carrier Kiosk",
            description="Fraudulent physical duplicate SIM issued using forged Aadhaar card",
            occurred_at=datetime.now(UTC) - timedelta(days=12),
            created_by=users["inv1"].id,
        )
        ev2 = CaseEvent(
            case_id=c1.id,
            title="Rapid Multilateral UPI Splitting",
            description="Funds dispersed across 14 beneficiary wallets within 8 minutes",
            occurred_at=datetime.now(UTC) - timedelta(days=11),
            created_by=users["inv1"].id,
        )
        ev3 = CaseEvent(
            case_id=c2.id,
            title="Late-night CAD Pattern Archive Upload",
            description="3.2 GB encrypted 7z archive transferred to offshore Mega.nz IP",
            occurred_at=datetime.now(UTC) - timedelta(days=7),
            created_by=users["inv2"].id,
        )
        ev4 = CaseEvent(
            case_id=c3.id,
            title="Credential Stuffing Intrusion on Pulse Secure VPN",
            description="Threat actor logged into administrative portal using compromised credentials",
            occurred_at=datetime.now(UTC) - timedelta(days=14),
            created_by=users["inv1"].id,
        )
        session.add_all([ev1, ev2, ev3, ev4])
        session.flush()

        for ev in [ev1, ev2, ev3, ev4]:
            append(
                session=session,
                actor=users["inv1"],
                action=AuditAction.EVENT_ADDED,
                case_id=ev.case_id,
                payload={"event_id": ev.id, "title": ev.title},
            )

        # Notes
        n1 = CaseNote(
            case_id=c1.id,
            body="Nodal cybercrime officer confirmed freezing order served on beneficiary bank accounts.",
            author_id=users["inv1"].id,
        )
        n2 = CaseNote(
            case_id=c2.id,
            body="Workstation forensic bitstream image acquired via Tableau T8u USB 3.0 write-blocker.",
            author_id=users["inv2"].id,
        )
        n3 = CaseNote(
            case_id=c3.id,
            body="Hospital EHR restored from offline air-gapped tape backup repository. No ransom paid.",
            author_id=users["inv1"].id,
        )
        session.add_all([n1, n2, n3])
        session.flush()

        for n in [n1, n2, n3]:
            append(
                session=session,
                actor=users["inv1"],
                action=AuditAction.NOTE_ADDED,
                case_id=n.case_id,
                payload={"note_id": n.id},
            )

        # 4. Ingest Evidence Items (~24 items)
        print("[5/6] Ingesting ~24 evidence items with cryptographic verification...")

        evidence_specs = [
            # Case 1 Evidence (UPI Fraud)
            (
                c1,
                users["inv1"],
                "statement_mule_4421.csv",
                "text/csv",
                EvidenceType.FILE,
                "State Bank Mule Statement",
                "Exported ledger reflecting 28 fraudulent transactions",
                "NetBanking Portal",
                "Core Banking",
                "Finacle",
                "v11.2",
                "CSV Statement Extract",
                b"Date,TxnID,Sender,Receiver,Amount,Status\n2026-10-18,TXN9901,ArunPatel,MuleAcct4421,480000,SUCCESS\n",
            ),
            (
                c1,
                users["inv1"],
                "chat_export_rohan.json",
                "application/json",
                EvidenceType.FILE,
                "WhatsApp Telegram Syndicate Chat",
                "Export of coordination group organizing mule withdrawals",
                "Seized iPhone 13",
                "Apple",
                "iPhone 13 Pro",
                "F2LZQ024MD6M",
                "UFED Physical Analyzer",
                json.dumps(
                    {
                        "group": "Fast Cash Surat",
                        "messages": [
                            {"from": "Rohan", "text": "Split 4.8L into 5 accounts immediately"}
                        ],
                    }
                ).encode("utf-8"),
            ),
            (
                c1,
                users["inv1"],
                "cctv_kiosk_atm_surat.png",
                "image/png",
                EvidenceType.FILE,
                "ATM CCTV Capture Surat",
                "High-definition still frame showing cash withdrawal by suspect",
                "Kiosk NVR",
                "Hikvision",
                "DS-7608NI",
                "HKV202609912",
                "Direct NVR Export",
                create_synthetic_png(),
            ),
            (
                c1,
                users["inv1"],
                "samsung_galaxy_s21_dump.dd",
                "application/octet-stream",
                EvidenceType.MOBILE_EXTRACT,
                "Samsung Galaxy S21 Physical Dump",
                "Complete bitstream disk image of mobile device seized from suspect",
                "Samsung S21",
                "Samsung",
                "SM-G991B",
                "R5CW2098VDA",
                "Cellebrite UFED 4PC",
                b"\x00\xff" * 2048,
            ),
            (
                c1,
                users["inv1"],
                "airtel_cdr_9820154321.xlsx",
                "application/octet-stream",
                EvidenceType.CLOUD_EXPORT,
                "Tower CDR and Location Logs",
                "Call Detail Records showing cell tower handover during SIM swap",
                "Carrier LEA Portal",
                "Airtel",
                "TowerCore",
                "LEA-CDR-409",
                "Secure LEA Portal",
                b"Cell ID,Azimuth,IMSI,IMEI,Duration\n40445,120,404450123456789,864201045987123,45\n",
            ),
            (
                c1,
                users["inv1"],
                "pcap_upi_gateway_spoof.pcap",
                "application/vnd.tcpdump.pcap",
                EvidenceType.NETWORK_CAPTURE,
                "UPI Gateway Network Capture",
                "Packet trace demonstrating reverse proxy spoofing and credential interception",
                "Gateway Tap",
                "Wireshark Tap",
                "SPAN-01",
                "PORT-8",
                "tcpdump 4.99",
                b"\xd4\xc3\xb2\xa1\x02\x00\x04\x00" + b"\x00" * 512,
            ),
            (
                c1,
                users["inv1"],
                "sandisk_cruzer_16gb.dd",
                "application/octet-stream",
                EvidenceType.DISK_IMAGE,
                "SanDisk USB Evidence Drive",
                "Physical flash drive containing automated transaction scripts",
                "USB Drive",
                "SanDisk",
                "Cruzer Blade 16GB",
                "SDCZ50-016G-11",
                "Guymager 0.8",
                b"AUTO_TRANSFER_ROUTINE_OCT2026\n" * 128,
            ),
            (
                c1,
                users["inv1"],
                "aadhaar_forgery_scan.png",
                "image/png",
                EvidenceType.FILE,
                "Forged Aadhaar Document Scan",
                "Scanned fraudulent Aadhaar card used to authorize unauthorized SIM swap",
                "Flatbed Scanner",
                "Canon",
                "LiDE 300",
                "CN99410283",
                "CanoScan Scan Utility",
                create_synthetic_png(),
            ),
            # Case 2 Evidence (Textile IP Theft)
            (
                c2,
                users["inv2"],
                "cad_jacquard_weave_2026.dwg",
                "application/octet-stream",
                EvidenceType.FILE,
                "Proprietary Jacquard Weave Schematics",
                "Confidential jacquard CAD schematics representing 8 months of R&D",
                "Workstation HDD",
                "Dell",
                "Precision 5820",
                "D5820-991A",
                "FTK Imager 4.7",
                b"DWG2026_AC1032_CONFIDENTIAL_WEAVE_MAP" * 32,
            ),
            (
                c2,
                users["inv2"],
                "auth_vpn_remote_access.log",
                "text/plain",
                EvidenceType.FILE,
                "Corporate OpenVPN Server Log",
                "Audit log showing 4:15 AM data transfer to unauthorized external IP",
                "VPN Gateway",
                "OpenVPN Inc",
                "AccessServer 2.11",
                "AS-SRV-02",
                "syslog daemon",
                b"2026-10-24 04:15:12 [GauravSen] CONNECTED 185.220.101.4\n2026-10-24 04:18:45 [GauravSen] UPLOAD 3435973836 bytes\n",
            ),
            (
                c2,
                users["inv2"],
                "mega_nz_upload_receipt.json",
                "application/json",
                EvidenceType.CLOUD_EXPORT,
                "Mega.nz Browser Cache Artifact",
                "Decrypted Chrome IndexedDB storage showing Mega.nz remote file handles",
                "User Profile",
                "Google",
                "Chrome 128",
                "IDX-DB-04",
                "Magnet AXIOM 7.2",
                json.dumps({"url": "https://mega.nz/file/ABC123#xyz", "size": 3435973836}).encode(
                    "utf-8"
                ),
            ),
            (
                c2,
                users["inv2"],
                "seagate_expansion_2tb_dump.dd",
                "application/octet-stream",
                EvidenceType.DISK_IMAGE,
                "Seagate 2TB Backup Drive Image",
                "Bitstream image of personal external hard drive seized during office search",
                "External HDD",
                "Seagate",
                "Expansion 2TB",
                "NA9X2811",
                "Tableau Forensic Imager",
                b"SEAGATE_PHYSICAL_RAW_IMAGE" * 256,
            ),
            (
                c2,
                users["inv2"],
                "supplier_contracts_decrypted.pdf",
                "application/pdf",
                EvidenceType.FILE,
                "Exfiltrated Global Supplier Contracts",
                "Proprietary pricing agreements with European yarn manufacturers",
                "Cloud Storage",
                "Adobe",
                "Acrobat XI",
                "PDF-EX-01",
                "Forensic PDF Validator",
                b"%PDF-1.5\n%SealTrail Synthetic Supplier Contracts Evidence\n%%EOF\n",
            ),
            (
                c2,
                users["inv2"],
                "kingston_datatraveler_32gb.dd",
                "application/octet-stream",
                EvidenceType.DISK_IMAGE,
                "Kingston DataTraveler USB Image",
                "Flash drive discovered inside suspect desk drawer",
                "USB Drive",
                "Kingston",
                "DataTraveler Exodia",
                "DTX-32GB-88",
                "AccessData FTK 4.5",
                b"KINGSTON_USB_SECTOR_0" * 128,
            ),
            (
                c2,
                users["inv2"],
                "slack_internal_export_oct.zip",
                "application/zip",
                EvidenceType.CLOUD_EXPORT,
                "Enterprise Slack Channel Audit Dump",
                "Exported direct messages revealing negotiations with competitor firm",
                "Slack Enterprise",
                "Slack Technologies",
                "eDiscovery API",
                "SLK-ED-2026",
                "Slack Compliance Export",
                b"PK\x03\x04" + b"\x00" * 256,
            ),
            (
                c2,
                users["inv2"],
                "browser_history_brave.sqlite",
                "application/x-sqlite3",
                EvidenceType.FILE,
                "Brave Browser History SQLite Database",
                "SQLite file showing web searches for 'how to wipe Windows event logs'",
                "Workstation SSD",
                "Brave Software",
                "Brave 1.68",
                "SQLITE-HIST-01",
                "SQLite Forensic Explorer",
                b"SQLite format 3\x00" + b"\x00" * 512,
            ),
            # Case 3 Evidence (Hospital Ransomware)
            (
                c3,
                users["inv1"],
                "akira_ransom_note.txt",
                "text/plain",
                EvidenceType.FILE,
                "Akira Ransomware Extortion Note",
                "Text document dropped into 42 server shares demanding 25 BTC",
                "Server Share",
                "Windows Server",
                "2022 Datacenter",
                "WIN-SRV-DC01",
                "PowerShell Copy",
                b"AKIRA RANSOMWARE. Your files are encrypted with RSA-4096. Contact us on Tor.\n",
            ),
            (
                c3,
                users["inv1"],
                "domain_controller_ram_dump.raw",
                "application/octet-stream",
                EvidenceType.FILE,
                "Primary Domain Controller RAM Dump",
                "Volatile physical memory captured before system shutdown",
                "DC-01 Physical Server",
                "HPE",
                "ProLiant DL380 Gen10",
                "SGH994012A",
                "WinPmem 4.0",
                b"\x55\xaa\x33\xcc" * 2048,
            ),
            (
                c3,
                users["inv1"],
                "powershell_event_4104_log.evtx",
                "application/octet-stream",
                EvidenceType.FILE,
                "PowerShell Script Block Logging Evtx",
                "Event log recording execution of encoded Mimikatz PowerShell payloads",
                "Event Log Directory",
                "Microsoft",
                "Windows Event Log",
                "EVTX-4104",
                "EnCase Forensic 21",
                b"ElfFile\x00" + b"\x00" * 512,
            ),
            (
                c3,
                users["inv1"],
                "firewall_c2_beaconing.log",
                "text/plain",
                EvidenceType.FILE,
                "Perimeter Firewall Beacon Log",
                "Outbound beaconing over HTTPS to Akira command-and-control server",
                "Core Firewall",
                "Fortinet",
                "FortiGate 200F",
                "FG200F-88912",
                "FortiOS Log Export",
                b'date=2026-10-17 time=02:14:09 devname="FG200F" srcip=10.0.1.15 dstip=194.26.29.111 proto=6 action=accept\n',
            ),
            (
                c3,
                users["inv1"],
                "phishing_lure_invoice.eml",
                "message/rfc822",
                EvidenceType.EMAIL,
                "Weaponized Phishing Email",
                "Inbound email containing macro-enabled malicious Excel invoice",
                "Exchange Server",
                "Microsoft",
                "Exchange 2019",
                "EXCH-MBOX-CMIO",
                "Exchange Message Tracker",
                b"From: billing@medical-equipment-supplier.com\nSubject: Overdue Maintenance Invoice OCT-2026\n\nPlease find invoice attached.\n",
            ),
            (
                c3,
                users["inv1"],
                "encrypted_sample_radiology.dcm",
                "application/dicom",
                EvidenceType.FILE,
                "Encrypted CT Scan Sample File",
                "Radiology scan encrypted with '.akira' file extension demonstrating payload execution",
                "PACS Storage",
                "GE Healthcare",
                "Centricity PACS",
                "PACS-STOR-01",
                "PACS Forensic Extraction",
                b"\x00" * 128 + b"DICM" + b"ENCRYPTED_AKIRA_PAYLOAD" * 64,
            ),
            (
                c3,
                users["inv1"],
                "backup_tape_verification_manifest.json",
                "application/json",
                EvidenceType.FILE,
                "LTO-8 Cold Backup Verification Manifest",
                "Verification audit manifest confirming clean restoration of 18 TB patient database",
                "Tape Library",
                "Quantum",
                "Scalar i3 LTO-8",
                "QUANT-LTO8-01",
                "Veeam Backup & Replication",
                json.dumps(
                    {
                        "backup_date": "2026-10-15",
                        "verification_sha256": "4a7b9c1d0e" * 6,
                        "status": "VERIFIED_CLEAN",
                    }
                ).encode("utf-8"),
            ),
            (
                c3,
                users["inv1"],
                "crowdstrike_endpoint_detection.json",
                "application/json",
                EvidenceType.CLOUD_EXPORT,
                "EDR Sensor Incident Telemetry",
                "Process tree analysis showing lateral movement via PsExec",
                "Cloud Falcon Console",
                "CrowdStrike",
                "Falcon Sensor",
                "CS-EDR-99",
                "Falcon Cloud API",
                json.dumps(
                    {
                        "incident_id": "INC-88912",
                        "technique": "T1021.002 Remote Services: SMB/Windows Admin Shares",
                    }
                ).encode("utf-8"),
            ),
        ]

        seeded_evidence: list[EvidenceItem] = []
        for (
            case_obj,
            investigator,
            filename,
            content_type,
            ev_type,
            item_name,
            desc,
            src_desc,
            make,
            model,
            serial,
            tool,
            raw_bytes,
        ) in evidence_specs:
            meta = {
                "type": ev_type.value,
                "item_name": item_name,
                "description": desc,
                "source_description": src_desc,
                "device_make": make,
                "device_model": model,
                "device_serial": serial,
                "acquisition_method": "Forensic Bitstream Acquisition",
                "acquisition_tool": tool,
                "collected_at": datetime.now(UTC) - timedelta(days=10),
            }
            stream = io.BytesIO(raw_bytes)
            ev_item, _ = intake.register_evidence(
                session=session,
                case=case_obj,
                user=investigator,
                file_stream=stream,
                original_filename=filename,
                content_type=content_type,
                metadata=meta,
            )
            ev_item.current_custodian_id = users["cust1"].id
            ev_item.current_location = "Evidence Vault Locker B-14"
            seeded_evidence.append(ev_item)

        session.flush()

        # Close Case 3 now that its evidence intake is complete
        c3.status = CaseStatus.CLOSED
        c3.closed_at = datetime.now(UTC) - timedelta(days=2)
        append(
            session=session,
            actor=users["sup2"],
            action=AuditAction.CASE_CLOSED,
            case_id=c3.id,
            payload={
                "reason": "Hospital ransomware remediated from cold backup; investigation completed."
            },
        )
        session.flush()

        # 5. Build Specific Required States
        print("[6/6] Establishing custody transfer chains, approvals, and compliance states...")

        # A. Clean custody trail with 3 transfers (Item 0)
        item0 = seeded_evidence[0]
        t1 = CustodyTransfer(
            evidence_id=item0.id,
            from_user_id=users["inv1"].id,
            to_user_id=users["cust1"].id,
            to_location="Main Vault Safe 1",
            reason="Initial intake vault handover",
            status=TransferStatus.COMPLETED,
            hash_at_send=item0.sha256,
            hash_at_receipt=item0.sha256,
            receipt_verified=True,
            requested_at=datetime.now(UTC) - timedelta(days=8),
            acknowledged_at=datetime.now(UTC) - timedelta(days=8, hours=-1),
        )
        t2 = CustodyTransfer(
            evidence_id=item0.id,
            from_user_id=users["cust1"].id,
            to_user_id=users["inv2"].id,
            to_location="Forensics Lab Terminal 3",
            reason="Secondary ledger analysis",
            status=TransferStatus.COMPLETED,
            hash_at_send=item0.sha256,
            hash_at_receipt=item0.sha256,
            receipt_verified=True,
            requested_at=datetime.now(UTC) - timedelta(days=5),
            acknowledged_at=datetime.now(UTC) - timedelta(days=5, hours=-1),
        )
        session.add_all([t1, t2])
        append(
            session=session,
            actor=users["inv1"],
            action=AuditAction.TRANSFER_REQUESTED,
            case_id=item0.case_id,
            evidence_id=item0.id,
            payload={"transfer_id": t1.id, "to_user": users["cust1"].email},
        )
        append(
            session=session,
            actor=users["cust1"],
            action=AuditAction.TRANSFER_ACKNOWLEDGED,
            case_id=item0.case_id,
            evidence_id=item0.id,
            payload={"transfer_id": t1.id, "receipt_verified": True},
        )

        # B. Transfer waiting for acknowledgement (Item 1)
        item1 = seeded_evidence[1]
        t_wait = CustodyTransfer(
            evidence_id=item1.id,
            from_user_id=users["cust1"].id,
            to_user_id=users["inv1"].id,
            to_location="Investigator Desk A-4",
            reason="Preparing court disclosure extract",
            status=TransferStatus.PENDING_ACK,
            hash_at_send=item1.sha256,
            requested_at=datetime.now(UTC) - timedelta(minutes=20),
            ack_due_at=datetime.now(UTC) + timedelta(minutes=settings.ACK_SLA_MINUTES - 20),
        )
        item1.status = EvidenceStatus.TRANSFER_PENDING
        session.add(t_wait)
        append(
            session=session,
            actor=users["cust1"],
            action=AuditAction.TRANSFER_REQUESTED,
            case_id=item1.case_id,
            evidence_id=item1.id,
            payload={"transfer_id": t_wait.id, "to_user": users["inv1"].email},
        )

        # C. Overdue transfer acknowledgement past SLA (Item 2)
        item2 = seeded_evidence[2]
        t_overdue = CustodyTransfer(
            evidence_id=item2.id,
            from_user_id=users["cust1"].id,
            to_user_id=users["inv2"].id,
            to_location="Facial Recognition Lab",
            reason="Biometric comparison against police database",
            status=TransferStatus.PENDING_ACK,
            hash_at_send=item2.sha256,
            requested_at=datetime.now(UTC) - timedelta(hours=3),
            ack_due_at=datetime.now(UTC) - timedelta(hours=2),
        )
        item2.status = EvidenceStatus.TRANSFER_PENDING
        session.add(t_overdue)
        append(
            session=session,
            actor=users["cust1"],
            action=AuditAction.TRANSFER_REQUESTED,
            case_id=item2.case_id,
            evidence_id=item2.id,
            payload={"transfer_id": t_overdue.id, "to_user": users["inv2"].email},
        )
        append(
            session=session,
            actor=None,
            action=AuditAction.ACK_OVERDUE,
            case_id=item2.case_id,
            evidence_id=item2.id,
            payload={"transfer_id": t_overdue.id, "overdue_minutes": 120},
        )

        # D. External transfer waiting for dual approval (Item 3)
        item3 = seeded_evidence[3]
        appr_ext = ApprovalRequest(
            kind=ApprovalKind.EXTERNAL_TRANSFER,
            case_id=item3.case_id,
            evidence_id=item3.id,
            requested_by=users["inv1"].id,
            justification="Transfer to Central Forensic Science Laboratory (CFSL) for chip-off recovery.",
            payload={"external_party": "CFSL New Delhi", "to_location": "CFSL Hardware Lab"},
            status=ApprovalStatus.PENDING,
            expires_at=datetime.now(UTC) + timedelta(hours=settings.APPROVAL_EXPIRY_HOURS),
        )
        session.add(appr_ext)
        append(
            session=session,
            actor=users["inv1"],
            action=AuditAction.APPROVAL_REQUESTED,
            case_id=item3.case_id,
            evidence_id=item3.id,
            payload={"approval_id": appr_ext.id, "kind": appr_ext.kind.value},
        )

        # E. Item under active Legal Hold (Item 4)
        item4 = seeded_evidence[4]
        retention.place_legal_hold_evidence(
            session=session,
            evidence_id=item4.id,
            actor=users["sup1"],
            reason="Preservation order issued by High Court under Section 91 CrPC",
        )

        # F. Item past retention and eligible for disposal (Item 5)
        item5 = seeded_evidence[5]
        item5.retention_until = date.today() - timedelta(days=15)
        item5.legal_hold = False

        # G. Off-hours view audit entry (simulated 2 AM access)
        append(
            session=session,
            actor=users["inv1"],
            action=AuditAction.EVIDENCE_VIEWED,
            case_id=c1.id,
            evidence_id=item0.id,
            payload={"action": "EVIDENCE_VIEWED", "note": "Off-hours forensic review"},
        )

        # H. Annotations on items
        ann1 = Annotation(
            evidence_id=item0.id,
            author_id=users["inv1"].id,
            body="Confirmed transaction TXN9901 originates from compromised Surat IP subnet.",
            body_sha256=audit_chain.compute_entry_hash("0" * 64, b"Confirmed transaction TXN9901"),
        )
        ann2 = Annotation(
            evidence_id=item1.id,
            author_id=users["inv2"].id,
            body="Telegram phone number cross-referenced against CDR logs with 100% correlation.",
            body_sha256=audit_chain.compute_entry_hash(
                "0" * 64, b"Telegram phone number cross-referenced"
            ),
        )
        session.add_all([ann1, ann2])
        append(
            session=session,
            actor=users["inv1"],
            action=AuditAction.EVIDENCE_ANNOTATED,
            case_id=item0.case_id,
            evidence_id=item0.id,
            payload={"annotation_id": ann1.id},
        )

        # I. Links connecting evidence to persons and events
        l1 = EvidenceLink(
            evidence_id=item0.id,
            target_type=LinkTargetType.PERSON,
            target_id=p1.id,
            relation="Beneficiary Account Holder",
            created_by=users["inv1"].id,
        )
        l2 = EvidenceLink(
            evidence_id=item0.id,
            target_type=LinkTargetType.EVENT,
            target_id=ev2.id,
            relation="Transaction Log Source",
            created_by=users["inv1"].id,
        )
        l3 = EvidenceLink(
            evidence_id=item1.id,
            target_type=LinkTargetType.PERSON,
            target_id=p1.id,
            relation="Suspect Communication Device",
            created_by=users["inv1"].id,
        )
        session.add_all([l1, l2, l3])
        append(
            session=session,
            actor=users["inv1"],
            action=AuditAction.EVIDENCE_LINKED,
            case_id=item0.case_id,
            evidence_id=item0.id,
            payload={"target_type": "PERSON", "target_id": p1.id, "relation": l1.relation},
        )

        session.flush()

        # Run anomaly detection rules to populate initial alerts
        print("Running security anomaly sweep...")
        anomaly.check_missing_acknowledgements(session)

        # Create signed checkpoint
        print("Generating signed Ed25519 chain checkpoint...")
        cp = checkpoints.create_checkpoint(session, created_by=users["admin"].id)
        if cp:
            append(
                session=session,
                actor=users["admin"],
                action=AuditAction.CHECKPOINT_CREATED,
                payload={"checkpoint_id": cp.id, "seq_to": cp.seq_to, "head_hash": cp.head_hash},
            )

        # Verify Chain
        print("Verifying complete audit chain integrity...")
        result = audit_chain.verify_chain(session)
        if not result.ok:
            raise RuntimeError(
                f"Seed failed chain verification: {result.reason} at seq #{result.first_broken_seq}"
            )

        session.commit()

        # Print summary
        print("\n" + "=" * 60)
        print("  SEALTRAIL SYNTHETIC SEED COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"  Personnel Accounts:      {len(users)}")
        print("  Active Cases:            3 (SL26-0042, SL26-0078, SL26-0105)")
        print(f"  Evidence Items Seeded:   {len(seeded_evidence)}")
        print(f"  Audit Entries Recorded:  {result.head_seq}")
        print("  Chain Integrity Status:  PASS (Strictly contiguous & signed)")
        print(f"  Default Login:           admin@{domain} / {settings.SEED_PASSWORD}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    seed_database()
