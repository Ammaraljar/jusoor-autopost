"""The kinds of newsletter a company can send. Each kind tells the AI how to write, which design
fits it best, how many sections it usually has and which material it draws on."""
from __future__ import annotations

from typing import Any

# id: (ar, en, ms, fr) names, (ar, en, ms, fr) descriptions, writing brief, design, sections, material
TYPES: dict[str, dict[str, Any]] = {
    "curated": {
        "name": ("النشرة التنسيقية", "Curated", "Kurasi", "Sélection"),
        "desc": ("أفضل الروابط والمقالات في مجالك من مصادر خارجية، في رسالة واحدة توفر وقت القارئ",
                 "The best links and articles in your field from outside sources, in one time-saving email",
                 "Pautan dan artikel terbaik dalam bidang anda daripada sumber luar, dalam satu e-mel",
                 "Les meilleurs liens et articles de votre secteur, réunis dans un seul e-mail"),
        "brief": "A curated digest: for each item give a one-line why-it-matters takeaway and credit the source. "
                 "Short sections, one per link; the reader should be able to scan it in 2 minutes.",
        "design": "digest", "sections": 6, "material": ["articles"],
    },
    "educational": {
        "name": ("النشرة التثقيفية والتعليمية", "Educational / How-to", "Pendidikan / Panduan", "Éducative / Tutoriel"),
        "desc": ("شروحات ونصائح وإرشادات عملية خطوة بخطوة لحل مشكلة أو تعلّم مهارة",
                 "Explanations, tips and practical step-by-step guidance to solve a problem or learn a skill",
                 "Penerangan, tip dan panduan langkah demi langkah untuk menyelesaikan masalah atau belajar kemahiran",
                 "Explications, conseils et étapes pratiques pour résoudre un problème ou apprendre"),
        "brief": "A how-to: open with the problem, then numbered practical steps or tips (one per section), "
                 "end with a quick summary. Teach, do not sell; at most one soft mention of the brand.",
        "design": "classic", "sections": 5, "material": ["topic", "posts"],
    },
    "reporting": {
        "name": ("النشرة الإخبارية / التقريرية", "News / Reporting", "Berita / Laporan", "Actualités / Reporting"),
        "desc": ("تغطية الأحداث الجارية والحقائق وأخبار قطاعك بشكل دوري ومحايد",
                 "Regular, neutral coverage of current events, facts and news from your sector",
                 "Liputan berkala dan neutral tentang peristiwa semasa, fakta dan berita sektor anda",
                 "Couverture régulière et neutre de l’actualité et des faits de votre secteur"),
        "brief": "News reporting: neutral, factual, the key facts first, attribute to sources, add what it means "
                 "for the reader in one line. No opinions, no exaggeration.",
        "design": "magazine", "sections": 5, "material": ["articles", "posts"],
    },
    "roundup": {
        "name": ("نشرة المقالات والمدونات", "Blog round-up", "Ringkasan blog", "Récap du blog"),
        "desc": ("ملخص لأحدث مقالاتك وتدويناتك ومنشوراتك لزيادة زوار موقعك",
                 "A summary of your latest articles and posts to bring readers to your website",
                 "Ringkasan artikel dan hantaran terkini anda untuk menarik pelawat ke laman web",
                 "Un résumé de vos derniers articles pour amener des visiteurs sur votre site"),
        "brief": "A round-up of the brand's own latest content: for each piece a teaser that makes people click "
                 "'read more'. Do not give away everything.",
        "design": "digest", "sections": 5, "material": ["posts"],
    },
    "story": {
        "name": ("نشرة السرد القصصي", "Storyteller", "Penceritaan", "Récit"),
        "desc": ("قصص واقعية وتجارب ومذكرات تبني علاقة إنسانية متينة مع المشتركين",
                 "Real stories, experiences and behind-the-scenes moments that build a human bond",
                 "Kisah benar, pengalaman dan di sebalik tabir yang membina hubungan mesra",
                 "Histoires vraies, expériences et coulisses qui créent un lien humain"),
        "brief": "Storytelling: one story told in the first person (we), with a beginning, a turning point and a "
                 "lesson; warm and personal; sections are chapters of the story. Only facts from the material.",
        "design": "minimal", "sections": 3, "material": ["topic", "posts"],
    },
    "analysis": {
        "name": ("النشرة التحليلية العميقة", "Deep dive / Analysis", "Analisis mendalam", "Analyse approfondie"),
        "desc": ("دراسات حالة وتحليلات مفصلة للسوق وإحصائيات مدعومة بالبيانات",
                 "Case studies, detailed market analysis and data-backed statistics",
                 "Kajian kes, analisis pasaran terperinci dan statistik berasaskan data",
                 "Études de cas, analyses de marché détaillées et statistiques chiffrées"),
        "brief": "A deep dive: context, the key numbers (exact, from the material only), what drives them, "
                 "implications and recommendations. Clear sub-headings; no invented data.",
        "design": "classic", "sections": 5, "material": ["topic", "articles", "posts"],
    },
    "promotional": {
        "name": ("النشرة الترويجية والتجارية", "Promotional", "Promosi", "Promotionnelle"),
        "desc": ("الإعلان عن منتجات جديدة وعروض خاصة وتخفيضات لزيادة المبيعات",
                 "New products, special offers and sales to drive revenue",
                 "Produk baharu, tawaran istimewa dan jualan untuk meningkatkan hasil",
                 "Nouveaux produits, offres spéciales et soldes pour vendre plus"),
        "brief": "A promotional email: a strong offer headline, benefit-led product sections each with a button, "
                 "clear urgency only if the material gives a deadline, one main call to action. Never invent "
                 "prices or discounts.",
        "design": "bold", "sections": 4, "material": ["products", "posts"],
    },
    "update": {
        "name": ("نشرة التحديثات المؤسسية", "Company / product update", "Kemas kini syarikat", "Nouvelles de l’entreprise"),
        "desc": ("ميزات أو خدمات جديدة، تغييرات في السياسات، أو إنجازات جديدة للعلامة",
                 "New features or services, policy changes or new milestones of the brand",
                 "Ciri atau perkhidmatan baharu, perubahan dasar atau pencapaian baharu",
                 "Nouveautés, changements de politique ou nouvelles réussites de la marque"),
        "brief": "A company update: what is new, why it matters for the customer, what (if anything) they need "
                 "to do, and thanks. Confident and transparent.",
        "design": "spotlight", "sections": 4, "material": ["topic", "posts", "products"],
    },
    "internal": {
        "name": ("النشرة الداخلية للموظفين", "Internal (employees)", "Dalaman (pekerja)", "Interne (équipe)"),
        "desc": ("لفريق العمل: أخبار الشركة، الترحيب بالموظفين الجدد، وتعزيز ثقافة العمل",
                 "For your team: company news, welcoming new colleagues and building the work culture",
                 "Untuk pasukan: berita syarikat, mengalu-alukan rakan baharu dan budaya kerja",
                 "Pour l’équipe : nouvelles de l’entreprise, bienvenue aux nouveaux et culture"),
        "brief": "An internal newsletter for employees: friendly colleague-to-colleague tone (no selling), "
                 "company news, wins and thanks, welcomes, reminders and dates. Address the team.",
        "design": "classic", "sections": 4, "material": ["topic"],
    },
    "survey": {
        "name": ("النشرة التفاعلية والاستطلاعية", "Survey / Community", "Tinjauan / Komuniti", "Sondage / Communauté"),
        "desc": ("سؤال أو استطلاع بنقرة واحدة، ومشاركة آراء ومحتوى العملاء أنفسهم",
                 "A one-click poll or question, and sharing your customers’ own opinions and content",
                 "Undian atau soalan satu klik, dan berkongsi pendapat serta kandungan pelanggan",
                 "Un sondage en un clic et le partage des avis et contenus de vos clients"),
        "brief": "A community email: invite the reader to answer one question (the poll is added below the intro), "
                 "explain why their opinion matters, and feature customer voices from the material if any.",
        "design": "minimal", "sections": 2, "material": ["topic", "posts"], "poll": True,
    },
    "event": {
        "name": ("نشرة المناسبات والفعاليات", "Event / Webinar invite", "Jemputan acara / Webinar", "Invitation à un événement"),
        "desc": ("دعوة لورشة أو ندوة رقمية أو مؤتمر مع تفاصيل الموعد والمكان والتسجيل",
                 "An invitation to a workshop, webinar or conference with date, place and registration",
                 "Jemputan ke bengkel, webinar atau persidangan dengan tarikh, tempat dan pendaftaran",
                 "Une invitation à un atelier, webinaire ou conférence avec date, lieu et inscription"),
        "brief": "An event invitation: what the event is, who it is for, what attendees will gain (agenda or "
                 "speakers as sections if given), and a clear 'register' call to action. The date, place and "
                 "registration link are shown in a box automatically.",
        "design": "spotlight", "sections": 3, "material": ["topic", "products"], "event": True,
    },
    "hybrid": {
        "name": ("النشرة الهجينة", "Hybrid", "Hibrid", "Hybride"),
        "desc": ("الأكثر شيوعًا: محتوى مفيد في الغالب (نحو 70%) مع عرض ترويجي (نحو 30%)",
                 "The most common: mostly useful content (about 70%) plus a promotion (about 30%)",
                 "Paling biasa: kebanyakan kandungan berguna (kira-kira 70%) dengan promosi (30%)",
                 "La plus courante : surtout du contenu utile (environ 70 %) et une promotion (30 %)"),
        "brief": "A hybrid email: about 70% genuinely useful content (tips, news, stories) and about 30% "
                 "promotion (the last sections), with one main call to action.",
        "design": "magazine", "sections": 5, "material": ["topic", "posts", "products"],
    },
}
LANG_INDEX = {"ar": 0, "en": 1, "ms": 2, "fr": 3}


def options() -> list[dict[str, Any]]:
    out = []
    for k, v in TYPES.items():
        out.append({"id": k, **{l: v["name"][i] for l, i in LANG_INDEX.items()},
                    "desc": {l: v["desc"][i] for l, i in LANG_INDEX.items()},
                    "design": v["design"], "sections": v["sections"], "material": v["material"],
                    "event": bool(v.get("event")), "poll": bool(v.get("poll"))})
    return out


def get(kind: str | None) -> dict[str, Any]:
    return TYPES.get(kind or "hybrid", TYPES["hybrid"])


def label(kind: str | None, lang: str) -> str:
    return get(kind)["name"][LANG_INDEX.get(lang, 1)]
