"""Industry profiles: everything the app adapts when a company picks its field.

Each profile drives the AI writer (who the brand is, who reads it, what "useful" means there,
how relevance is judged), the defaults of a new company (tone, content type, CTA, photo
keywords, colours) and the labels shown in the dashboard.
"""
from __future__ import annotations

from typing import Any

INDUSTRIES: dict[str, dict[str, Any]] = {
    "travel": {
        "ar": "السفر والسياحة", "en": "Travel & tourism",
        "brand_type": "travel and tourism company",
        "audience": {"ar": "مسافرون عرب وعائلات يبحثون عن وجهات وبرامج سياحية",
                     "en": "travellers and families looking for destinations and holiday packages"},
        "objective": "build trust and turn followers into bookings",
        "value": "a practical travel tip, the best time to go, what to see, how to save, what the news means for a trip",
        "relevance": "travel, tourism, destinations, airlines, hotels, visas and holidays",
        "tone": "friendly", "content_type": "travel", "image_keywords": "travel destination landmark",
        "cta": "خطّط رحلتك القادمة معنا", "cta_en": "Plan your next trip with us",
        "colors": {"navy": "#16244F", "gold": "#C6A23C"},
    },
    "news": {
        "ar": "الأخبار والإعلام", "en": "News & media",
        "brand_type": "news and media outlet",
        "audience": {"ar": "قرّاء يتابعون الأخبار ويريدون الخلاصة بسرعة ودقة",
                     "en": "readers who want the essential facts quickly and accurately"},
        "objective": "inform accurately, grow followers and drive clicks to the full story",
        "value": "the key facts, why it matters, what happens next, numbers and context — strictly neutral",
        "relevance": "newsworthy, verified and of public interest to the outlet's audience",
        "tone": "professional", "content_type": "news", "image_keywords": "news city people",
        "cta": "تابعونا لآخر الأخبار", "cta_en": "Follow us for the latest news",
        "colors": {"navy": "#1B1F3B", "gold": "#E63946"},
        "rules": "Stay strictly neutral and factual. No opinions, no exaggeration, attribute claims to their source.",
    },
    "tech": {
        "ar": "التقنية والبرمجيات", "en": "Technology & software",
        "brand_type": "technology company",
        "audience": {"ar": "مهتمون بالتقنية وأصحاب أعمال يبحثون عن حلول رقمية",
                     "en": "tech-savvy users and business owners looking for digital solutions"},
        "objective": "show expertise, explain technology simply and generate leads",
        "value": "a simple explanation, a how-to, a feature that saves time, a security tip, a comparison",
        "relevance": "technology, software, AI, digital products, cybersecurity and innovation",
        "tone": "professional", "content_type": "educational", "image_keywords": "technology laptop office",
        "cta": "تواصل معنا لحلول تقنية تناسب عملك", "cta_en": "Talk to us about the right tech for your business",
        "colors": {"navy": "#0F2A44", "gold": "#2EC4B6"},
    },
    "restaurants": {
        "ar": "المطاعم والكافيهات", "en": "Restaurants & cafés",
        "brand_type": "restaurant / café",
        "audience": {"ar": "محبو الأكل والقهوة والعائلات الباحثة عن تجربة لذيذة قريبة",
                     "en": "food and coffee lovers and families looking for a great place nearby"},
        "objective": "make people hungry, bring them in and drive orders and reservations",
        "value": "the dish and what makes it special, ingredients, the experience, opening times, offers, pairings",
        "relevance": "food, drinks, dining, coffee culture and the restaurant's own news",
        "tone": "friendly", "content_type": "promotional", "image_keywords": "food restaurant coffee",
        "cta": "احجز طاولتك أو اطلب الآن", "cta_en": "Book your table or order now",
        "colors": {"navy": "#3B1F14", "gold": "#E9A23B"},
    },
    "education": {
        "ar": "المدارس والجامعات والتعليم", "en": "Schools & universities",
        "brand_type": "educational institution (school, institute or university)",
        "audience": {"ar": "طلاب وأولياء أمور يبحثون عن تعليم موثوق",
                     "en": "students and parents looking for trusted education"},
        "objective": "build credibility, show outcomes and drive enrolments",
        "value": "a study tip, admission dates and steps, programme benefits, career outcomes, student success",
        "relevance": "education, learning, admissions, scholarships, training and careers",
        "tone": "educational", "content_type": "educational", "image_keywords": "students classroom university",
        "cta": "سجّل الآن أو تواصل مع القبول", "cta_en": "Enrol now or contact admissions",
        "colors": {"navy": "#123A6B", "gold": "#F2B134"},
    },
    "ecommerce": {
        "ar": "المتاجر الإلكترونية", "en": "Online stores (e-commerce)",
        "brand_type": "online store",
        "audience": {"ar": "متسوقون أونلاين يبحثون عن منتجات جيدة وعروض",
                     "en": "online shoppers looking for quality products and good deals"},
        "objective": "show products clearly, answer objections and drive sales",
        "value": "the product benefit, how to use it, who it is for, the offer and delivery details",
        "relevance": "products, shopping, offers, delivery and the store's catalogue",
        "tone": "bold", "content_type": "product", "image_keywords": "product shopping lifestyle",
        "cta": "اطلب الآن — التوصيل سريع", "cta_en": "Order now — fast delivery",
        "colors": {"navy": "#1E1B4B", "gold": "#F59E0B"},
    },
    "realestate": {
        "ar": "العقارات", "en": "Real estate",
        "brand_type": "real estate company",
        "audience": {"ar": "باحثون عن سكن واستثمار عقاري", "en": "home seekers and property investors"},
        "objective": "present properties attractively, build trust and generate viewing requests",
        "value": "location advantages, space and features, price range if given, investment return, buying steps",
        "relevance": "property, housing, investment, neighbourhoods and the property market",
        "tone": "professional", "content_type": "promotional", "image_keywords": "modern apartment house interior",
        "cta": "احجز معاينة اليوم", "cta_en": "Book a viewing today",
        "colors": {"navy": "#1F2937", "gold": "#B08D57"},
    },
    "fashion": {
        "ar": "الموضة والتسوق", "en": "Fashion & shopping",
        "brand_type": "fashion brand / boutique",
        "audience": {"ar": "محبو الموضة والأناقة", "en": "style-conscious shoppers"},
        "objective": "inspire, show the look and drive store visits and orders",
        "value": "how to style it, the occasion, the fabric and fit, the trend, the offer",
        "relevance": "fashion, style, beauty, accessories, trends and shopping",
        "tone": "luxury", "content_type": "product", "image_keywords": "fashion style model",
        "cta": "اكتشف التشكيلة الآن", "cta_en": "Discover the collection",
        "colors": {"navy": "#111111", "gold": "#C9A27E"},
    },
    "health": {
        "ar": "الصحة والعيادات", "en": "Health & clinics",
        "brand_type": "clinic / healthcare provider",
        "audience": {"ar": "أفراد وعائلات يهتمون بصحتهم", "en": "people and families who care about their health"},
        "objective": "educate responsibly, build trust and drive appointments",
        "value": "a prevention tip, when to see a doctor, what a service involves, clinic hours",
        "relevance": "health, wellbeing, medical services and the clinic's specialities",
        "tone": "professional", "content_type": "educational", "image_keywords": "healthcare clinic doctor",
        "cta": "احجز موعدك الآن", "cta_en": "Book your appointment",
        "colors": {"navy": "#0B3C5D", "gold": "#3CB4A3"},
        "rules": "Give general information only, never diagnoses or dosages; advise consulting a doctor.",
    },
    "beauty": {
        "ar": "التجميل والصالونات", "en": "Beauty & salons",
        "brand_type": "beauty salon / spa",
        "audience": {"ar": "مهتمات ومهتمون بالعناية والجمال", "en": "people who love self-care and beauty"},
        "objective": "show results, inspire and drive bookings",
        "value": "the treatment and its result, care tips, before-and-after story, the offer",
        "relevance": "beauty, skincare, hair, spa and wellness",
        "tone": "friendly", "content_type": "promotional", "image_keywords": "beauty spa skincare",
        "cta": "احجزي موعدك الآن", "cta_en": "Book your session",
        "colors": {"navy": "#4A1D3F", "gold": "#E7B9A3"},
    },
    "automotive": {
        "ar": "السيارات", "en": "Automotive",
        "brand_type": "car dealer / automotive service",
        "audience": {"ar": "مهتمون بالسيارات ومشترون محتملون", "en": "car enthusiasts and buyers"},
        "objective": "showcase cars and services and drive test drives and visits",
        "value": "key specs in plain words, ownership tips, maintenance advice, the offer",
        "relevance": "cars, mobility, maintenance and the automotive market",
        "tone": "bold", "content_type": "product", "image_keywords": "car automotive road",
        "cta": "احجز تجربة قيادة", "cta_en": "Book a test drive",
        "colors": {"navy": "#111827", "gold": "#DC2626"},
    },
    "events": {
        "ar": "الفعاليات والمؤتمرات", "en": "Events & conferences",
        "brand_type": "events and conferences organiser",
        "audience": {"ar": "حضور محتملون ومهنيون ورعاة", "en": "potential attendees, professionals and sponsors"},
        "objective": "build anticipation and drive registrations",
        "value": "what attendees gain, speakers, agenda highlights, dates and registration steps",
        "relevance": "events, conferences, exhibitions, workshops and networking",
        "tone": "professional", "content_type": "event", "image_keywords": "conference event audience",
        "cta": "سجّل مقعدك الآن", "cta_en": "Register your seat now",
        "colors": {"navy": "#1A1446", "gold": "#F5B700"},
    },
    "training": {
        "ar": "التدريب والتأهيل", "en": "Training & professional development",
        "brand_type": "training and professional development provider",
        "audience": {"ar": "موظفون ومهنيون ومؤسسات يبحثون عن تطوير المهارات وشهادات معتمدة",
                     "en": "professionals, teams and organisations looking to build skills and earn accredited certificates"},
        "objective": "show expertise and outcomes, build credibility and fill training programmes",
        "value": "a skill tip, what participants will be able to do, accreditation, programme dates and format, career impact",
        "relevance": "skills, training, professional development, certifications, leadership and the workplace",
        "tone": "professional", "content_type": "educational", "image_keywords": "training workshop professionals",
        "cta": "سجّل في البرنامج الآن", "cta_en": "Register for the programme now",
        "colors": {"navy": "#0E3B43", "gold": "#E0A526"},
    },
    "nonprofit": {
        "ar": "المنظمات غير الربحية", "en": "Non-profit organisations",
        "brand_type": "non-profit / charitable organisation",
        "audience": {"ar": "متبرعون ومتطوعون وشركاء ومجتمع يهتم بالأثر الإنساني",
                     "en": "donors, volunteers, partners and a community that cares about impact"},
        "objective": "show real impact, build trust and move people to donate, volunteer or share",
        "value": "a real story, the impact in numbers, the need, how to help, transparency about results",
        "relevance": "the cause, community, humanitarian work, volunteering, campaigns and partnerships",
        "tone": "emotional", "content_type": "storytelling", "image_keywords": "community volunteers people helping",
        "cta": "كن جزءًا من الأثر — تبرّع أو تطوّع", "cta_en": "Be part of the impact — donate or volunteer",
        "colors": {"navy": "#123B2E", "gold": "#F2A541"},
        "rules": "Be respectful and dignified with people in need; no guilt-tripping, no exaggerated numbers.",
    },
    "general": {
        "ar": "مجال آخر / عام", "en": "Other / general business",
        "brand_type": "business",
        "audience": {"ar": "عملاء الشركة ومتابعوها", "en": "the company's customers and followers"},
        "objective": "build trust, engagement and leads",
        "value": "a useful tip, a clear benefit, what the news means for the customer",
        "relevance": "the company's field and its customers' interests",
        "tone": "friendly", "content_type": "educational", "image_keywords": "business people office",
        "cta": "تواصل معنا اليوم", "cta_en": "Contact us today",
        "colors": {"navy": "#16244F", "gold": "#C6A23C"},
    },
}

LANGUAGES = {"ar": "العربية", "en": "English", "ms": "Bahasa Melayu", "fr": "Français"}

# Labels and calls to action in Malay and French; card design family for each field
EXTRA: dict[str, dict[str, str]] = {
    "travel": {"ms": "Pelancongan & perjalanan", "fr": "Voyage & tourisme", "design": "travel",
               "cta_ms": "Rancang percutian anda bersama kami", "cta_fr": "Planifiez votre prochain voyage avec nous"},
    "news": {"ms": "Berita & media", "fr": "Actualités & médias", "design": "news",
             "cta_ms": "Ikuti kami untuk berita terkini", "cta_fr": "Suivez-nous pour l’actualité"},
    "tech": {"ms": "Teknologi & perisian", "fr": "Technologie & logiciels", "design": "tech",
             "cta_ms": "Hubungi kami untuk penyelesaian teknologi", "cta_fr": "Parlons de la bonne solution pour vous"},
    "restaurants": {"ms": "Restoran & kafe", "fr": "Restaurants & cafés", "design": "food",
                    "cta_ms": "Tempah meja atau pesan sekarang", "cta_fr": "Réservez ou commandez maintenant"},
    "education": {"ms": "Sekolah & universiti", "fr": "Écoles & universités", "design": "education",
                  "cta_ms": "Daftar sekarang", "cta_fr": "Inscrivez-vous dès maintenant"},
    "training": {"ms": "Latihan & pembangunan profesional", "fr": "Formation & développement professionnel",
                 "design": "training", "cta_ms": "Daftar program sekarang", "cta_fr": "Inscrivez-vous au programme"},
    "nonprofit": {"ms": "Organisasi bukan untung", "fr": "Associations & ONG", "design": "nonprofit",
                  "cta_ms": "Jadi sebahagian daripada impak — derma atau jadi sukarelawan",
                  "cta_fr": "Participez — faites un don ou devenez bénévole"},
    "ecommerce": {"ms": "Kedai dalam talian", "fr": "E-commerce", "design": "retail",
                  "cta_ms": "Pesan sekarang — penghantaran pantas", "cta_fr": "Commandez maintenant — livraison rapide"},
    "realestate": {"ms": "Hartanah", "fr": "Immobilier", "design": "luxury",
                   "cta_ms": "Tempah lawatan hari ini", "cta_fr": "Réservez une visite"},
    "fashion": {"ms": "Fesyen", "fr": "Mode", "design": "fashion",
                "cta_ms": "Terokai koleksi", "cta_fr": "Découvrez la collection"},
    "health": {"ms": "Kesihatan & klinik", "fr": "Santé & cliniques", "design": "health",
               "cta_ms": "Tempah janji temu anda", "cta_fr": "Prenez rendez-vous"},
    "beauty": {"ms": "Kecantikan & salun", "fr": "Beauté & salons", "design": "beauty",
               "cta_ms": "Tempah sesi anda", "cta_fr": "Réservez votre séance"},
    "automotive": {"ms": "Automotif", "fr": "Automobile", "design": "auto",
                   "cta_ms": "Tempah pandu uji", "cta_fr": "Réservez un essai"},
    "events": {"ms": "Acara & persidangan", "fr": "Événements & conférences", "design": "events",
               "cta_ms": "Daftar tempat anda sekarang", "cta_fr": "Réservez votre place"},
    "general": {"ms": "Perniagaan umum", "fr": "Autre / activité générale", "design": "general",
                "cta_ms": "Hubungi kami hari ini", "cta_fr": "Contactez-nous aujourd’hui"},
}
for _k, _v in EXTRA.items():
    INDUSTRIES[_k].update(_v)


def get(industry: str | None) -> dict[str, Any]:
    return INDUSTRIES.get(industry or "travel", INDUSTRIES["general"])


def options() -> list[dict[str, str]]:
    return [{"id": k, "ar": v["ar"], "en": v["en"], "ms": v["ms"], "fr": v["fr"]} for k, v in INDUSTRIES.items()]


def audience(profile: dict[str, Any], language: str) -> str:
    return profile["audience"]["ar" if language == "ar" else "en"]


def cta(profile: dict[str, Any], language: str) -> str:
    return profile["cta"] if language == "ar" else profile.get(f"cta_{language}") or profile["cta_en"]


def label(industry: str | None, language: str = "ar") -> str:
    p = get(industry)
    return p.get(language) or p["en"]


def generation_defaults(industry: str, language: str = "ar", dialect: str | None = None) -> dict[str, Any]:
    p = get(industry)
    return {"language": language, "tone": p["tone"], "content_type": p["content_type"],
            "audience": audience(p, language), "objective": p["objective"],
            "industry": industry, "dialect": dialect or "msa"}
