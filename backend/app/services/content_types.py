"""Kinds of content, per field: each field offers the kinds that fit it, and each kind tells the
writer what the post must be (so a clinic gets health awareness and doctor's tips, a travel agency
destinations and itineraries, a restaurant dishes and recipes…).
"""
from __future__ import annotations

# id: (Arabic, English, Malay, French, what the writer must produce)
CATALOG: dict[str, tuple[str, str, str, str, str]] = {
    "news": ("أخبار المجال", "Field news", "Berita bidang", "Actualités du secteur",
             "News of the field: what happened, when, and what it changes for the reader."),
    "breaking": ("خبر عاجل", "Breaking news", "Berita terkini", "Dernière minute",
                 "Breaking news: the key fact first, then who/where/when, then what is still unknown. No speculation."),
    "analysis": ("تحليل وقراءة", "Analysis", "Analisis", "Analyse",
                 "Analysis: the context, the causes, the numbers that matter and what to expect next."),
    "tips": ("نصائح عملية", "Practical tips", "Tip praktikal", "Conseils pratiques",
             "Practical tips: one concrete, actionable tip per slide."),
    "guide": ("دليل خطوة بخطوة", "Step-by-step guide", "Panduan langkah demi langkah", "Guide pas à pas",
              "A step-by-step guide: numbered steps the reader can follow."),
    "educational": ("معلومة تعليمية", "Educational", "Pendidikan", "Éducatif",
                    "Educational: explain one idea simply, with an example."),
    "faq": ("أسئلة شائعة", "FAQ", "Soalan lazim", "FAQ",
            "Frequently asked questions: one real customer question and its clear answer per slide."),
    "myths": ("خرافات وحقائق", "Myths vs facts", "Mitos vs fakta", "Idées reçues",
              "Myths vs facts: a common belief, then the correct fact, per slide."),
    "checklist": ("قائمة تحقق", "Checklist", "Senarai semak", "Check-list",
                  "A checklist the reader can save: short items to tick."),
    "comparison": ("مقارنة", "Comparison", "Perbandingan", "Comparatif",
                   "A fair comparison of options with the criteria that matter."),
    "promotional": ("ترويجي", "Promotional", "Promosi", "Promotionnel",
                    "Promotional: the offer or service, its benefit, who it is for and how to get it. No invented prices."),
    "product": ("منتج أو خدمة", "Product / service", "Produk / perkhidmatan", "Produit / service",
                "One product or service: what it is, its main benefits, who it suits, how to order."),
    "storytelling": ("قصة", "Story", "Cerita", "Histoire",
                     "A short story with a beginning, a turning point and a lesson that relates to the brand."),
    "testimonial": ("تجربة عميل", "Customer story", "Kisah pelanggan", "Témoignage",
                    "A customer's experience (only from the source): the need, the experience, the result."),
    "behind_scenes": ("خلف الكواليس", "Behind the scenes", "Di sebalik tabir", "Coulisses",
                      "Behind the scenes: the team, the process or the care behind the service."),
    "announcement": ("إعلان", "Announcement", "Pengumuman", "Annonce",
                     "An official announcement: what, when, where, and what the reader should do."),
    "corporate": ("أخبار الشركة", "Company news", "Berita syarikat", "Vie de l’entreprise",
                  "Company news: the milestone and what it means for customers."),
    "event": ("فعالية", "Event", "Acara", "Événement",
              "An event: what, when, where, who it is for and how to register."),
    # travel
    "travel": ("محتوى سياحي", "Travel content", "Kandungan pelancongan", "Contenu voyage",
               "Travel content: places, experiences and practical advice for travellers."),
    "destination": ("وجهة سياحية", "Destination", "Destinasi", "Destination",
                    "A destination: why go, best time, top experiences, practical tips."),
    "itinerary": ("برنامج رحلة", "Itinerary", "Jadual perjalanan", "Itinéraire",
                  "An itinerary: the trip day by day with the highlights of each day."),
    "travel_deals": ("عروض السفر", "Travel deals", "Tawaran pelancongan", "Offres de voyage",
                     "A travel offer: destination, duration, what is included, who it suits. Prices only if given."),
    "travel_tips": ("نصائح المسافر", "Traveller tips", "Tip pengembara", "Conseils voyageurs",
                    "Advice for travellers: visas, packing, money, transport, etiquette."),
    # restaurants
    "dish": ("طبق اليوم", "Dish of the day", "Hidangan hari ini", "Plat du jour",
             "One dish: its taste, ingredients and the moment to enjoy it."),
    "recipe": ("وصفة", "Recipe", "Resipi", "Recette",
               "A simple recipe: ingredients, then short numbered steps."),
    "menu": ("من قائمتنا", "From our menu", "Dari menu kami", "Notre carte",
             "Items from the menu grouped by mood or occasion."),
    # health
    "health_awareness": ("توعية صحية", "Health awareness", "Kesedaran kesihatan", "Sensibilisation santé",
                         "Health awareness: signs, prevention and when to see a doctor. No diagnosis, no cures promised."),
    "doctor_tip": ("نصيحة الطبيب", "Doctor's tip", "Tip doktor", "Conseil du médecin",
                   "A doctor's practical advice on one topic, safe and general."),
    "clinic_service": ("خدمة العيادة", "Clinic service", "Perkhidmatan klinik", "Service de la clinique",
                       "A clinic service: who needs it, how it works, what to expect, how to book."),
    # beauty & fashion
    "before_after": ("قبل وبعد", "Before & after", "Sebelum & selepas", "Avant / après",
                     "Before and after: the starting point, what was done, the result (only real results from the source)."),
    "beauty_tips": ("نصائح العناية والجمال", "Beauty & care tips", "Tip kecantikan", "Conseils beauté",
                    "Beauty and care tips that are safe and easy to follow at home."),
    "trend": ("صيحات وموضة", "Trends", "Trend", "Tendances",
              "This season's trends and how to wear or use them."),
    "lookbook": ("إطلالات وتنسيقات", "Lookbook", "Gaya", "Lookbook",
                 "Outfit or look ideas: pieces, how to combine them, for which occasion."),
    "new_arrivals": ("وصل حديثًا", "New arrivals", "Baru tiba", "Nouveautés",
                     "New arrivals: the new items and what makes each one special."),
    # real estate
    "property_listing": ("عقار معروض", "Property listing", "Hartanah dijual", "Bien à vendre / louer",
                         "One property: location, size, rooms, features, who it suits. Price only if given."),
    "market_insight": ("قراءة في السوق", "Market insight", "Tinjauan pasaran", "Point marché",
                       "Market insight: the trend, the numbers from the source and what it means for buyers/investors."),
    "buyer_guide": ("دليل المشتري", "Buyer's guide", "Panduan pembeli", "Guide de l’acheteur",
                    "A guide for buyers or tenants: steps, documents, mistakes to avoid."),
    # education & training
    "course_promo": ("إعلان دورة", "Course spotlight", "Sorotan kursus", "Formation à la une",
                     "One course: what the learner will be able to do, for whom, duration, certificate, how to enrol."),
    "success_story": ("قصة نجاح", "Success story", "Kisah kejayaan", "Réussite",
                      "A learner's or graduate's success (only from the source): the start, the effort, the result."),
    "skill_tip": ("مهارة في دقيقة", "Skill in a minute", "Kemahiran seminit", "Une compétence en une minute",
                  "One professional skill explained in short practical steps."),
    "campus_life": ("حياة الطلاب", "Campus life", "Kehidupan kampus", "Vie du campus",
                    "Student life: activities, facilities, achievements and moments."),
    "admission": ("القبول والتسجيل", "Admissions", "Kemasukan", "Admissions",
                  "Admissions: programmes, dates, requirements and how to apply."),
    # tech & ecommerce
    "tech_explainer": ("شرح تقني مبسّط", "Tech explainer", "Penerangan teknologi", "Explication tech",
                       "A technical idea explained simply with a real-life example."),
    "feature_release": ("ميزة جديدة", "New feature", "Ciri baharu", "Nouvelle fonctionnalité",
                        "A new feature or update: what it does, why it matters, how to use it."),
    "use_case": ("حالة استخدام", "Use case", "Kes penggunaan", "Cas d’usage",
                 "A use case: the problem, how the product solves it, the result."),
    "deal": ("عرض وتخفيض", "Deal", "Tawaran", "Promo",
             "A deal: the product, the saving, the deadline and how to buy. Only real figures."),
    # automotive & car rental
    "car_review": ("استعراض سيارة", "Car spotlight", "Sorotan kereta", "Focus voiture",
                   "One car: design, comfort, performance, who it suits."),
    "maintenance_tip": ("نصيحة صيانة", "Maintenance tip", "Tip penyelenggaraan", "Conseil d’entretien",
                        "A car maintenance tip: the sign, the reason, what to do."),
    "rental_offer": ("عرض تأجير", "Rental offer", "Tawaran sewa", "Offre de location",
                     "A rental offer: the car, the duration, what is included, how to book. Prices only if given."),
    "road_trip": ("رحلة بالسيارة", "Road trip idea", "Idea perjalanan darat", "Idée de road trip",
                  "A road-trip idea: route, stops, driving time and tips."),
    # events
    "event_agenda": ("برنامج الفعالية", "Event agenda", "Agenda acara", "Programme",
                     "The event agenda: sessions and times, what attendees will gain."),
    "speakers": ("المتحدثون", "Speakers", "Penceramah", "Intervenants",
                 "The speakers: who they are and what they will talk about."),
    "recap": ("ملخص الفعالية", "Event recap", "Ringkasan acara", "Retour sur l’événement",
              "An event recap: highlights, numbers and memorable moments."),
    # nonprofit & government
    "impact": ("أثر وإنجازات", "Impact", "Impak", "Impact",
               "Impact: what was achieved, for whom, with the real numbers from the source."),
    "donation_call": ("دعوة للتبرع أو التطوع", "Call to give / volunteer", "Seruan menderma", "Appel au don",
                      "A call to donate or volunteer: the need, what the help achieves, how to take part."),
    "awareness": ("توعية مجتمعية", "Public awareness", "Kesedaran awam", "Sensibilisation",
                  "Public awareness: the issue, why it matters, what each person can do."),
    "public_service": ("خدمة للمواطن", "Public service", "Perkhidmatan awam", "Service public",
                       "A public service: who can use it, the steps, the documents and the channels."),
    "regulation": ("أنظمة وقرارات", "Rules & decisions", "Peraturan & keputusan", "Règles et décisions",
                   "A new rule or decision: what changes, from when, who is concerned, what to do."),
}

BY_INDUSTRY: dict[str, list[str]] = {
    "travel": ["travel", "destination", "itinerary", "travel_deals", "travel_tips", "news", "guide", "faq",
               "testimonial", "checklist", "storytelling", "promotional"],
    "news": ["news", "breaking", "analysis", "educational", "faq", "myths", "storytelling", "announcement"],
    "tech": ["tech_explainer", "feature_release", "use_case", "educational", "news", "tips", "guide", "comparison", "faq",
             "myths", "product", "corporate", "event"],
    "restaurants": ["dish", "menu", "recipe", "promotional", "behind_scenes", "testimonial", "event", "tips",
                    "announcement", "storytelling"],
    "education": ["admission", "campus_life", "success_story", "educational", "tips", "event", "announcement",
                  "faq", "news", "course_promo"],
    "ecommerce": ["product", "new_arrivals", "deal", "promotional", "comparison", "guide", "faq", "testimonial",
                  "tips", "behind_scenes"],
    "realestate": ["property_listing", "market_insight", "buyer_guide", "tips", "faq", "news", "comparison",
                   "testimonial", "promotional", "checklist"],
    "fashion": ["new_arrivals", "lookbook", "trend", "product", "deal", "promotional", "tips", "behind_scenes",
                "testimonial"],
    "health": ["health_awareness", "doctor_tip", "clinic_service", "myths", "faq", "checklist", "news",
               "testimonial", "announcement", "educational"],
    "beauty": ["before_after", "beauty_tips", "trend", "promotional", "deal", "faq", "myths", "behind_scenes",
               "testimonial"],
    "automotive": ["car_review", "product", "maintenance_tip", "comparison", "deal", "promotional", "news", "faq", "guide",
                   "testimonial"],
    "events": ["event", "event_agenda", "speakers", "recap", "announcement", "news", "behind_scenes", "faq"],
    "training": ["course_promo", "skill_tip", "success_story", "educational", "tips", "event", "faq", "checklist",
                 "testimonial", "announcement"],
    "nonprofit": ["impact", "storytelling", "donation_call", "awareness", "event", "announcement", "news",
                  "behind_scenes"],
    "government": ["public_service", "regulation", "awareness", "announcement", "news", "faq", "event", "guide"],
    "car_rental": ["rental_offer", "car_review", "road_trip", "travel_tips", "deal", "faq", "testimonial",
                   "maintenance_tip", "promotional"],
    "general": ["educational", "tips", "promotional", "product", "news", "storytelling", "faq", "testimonial",
                "behind_scenes", "announcement", "event", "comparison"],
}


def for_industry(industry: str | None) -> list[str]:
    return BY_INDUSTRY.get(industry or "general", BY_INDUSTRY["general"])


def options() -> dict[str, dict[str, str]]:
    return {k: {"ar": v[0], "en": v[1], "ms": v[2], "fr": v[3]} for k, v in CATALOG.items()}


def guidance(content_type: str | None) -> str:
    entry = CATALOG.get(content_type or "")
    return entry[4] if entry else ""


def label(content_type: str | None, lang: str = "en") -> str:
    entry = CATALOG.get(content_type or "")
    if not entry:
        return content_type or ""
    return entry[{"ar": 0, "en": 1, "ms": 2, "fr": 3}.get(lang, 1)]
