import { createContext, useContext, useEffect, useState } from 'react';

const dict = {
  ar: {
    appName: 'جسور — النشر الذكي', appSub: 'منصة المحتوى الآلي',
    nav_review: 'قائمة المراجعة', nav_sources: 'المصادر', nav_calendar: 'التقويم', nav_campaigns: 'الحملات',
    nav_brand: 'الهوية البصرية', nav_stats: 'الإحصاءات', nav_settings: 'الإعدادات',
    logout: 'خروج', language: 'English', theme: 'الوضع',
    st_all: 'الكل', st_generating: 'قيد التوليد', st_pending_review: 'بانتظار المراجعة', st_approved: 'جاهزة للنشر',
    st_scheduled: 'مجدولة', st_publishing: 'قيد النشر', st_published: 'منشورة', st_failed: 'فشلت', st_rejected: 'مرفوضة',
    today: 'اليوم', yesterday: 'أمس', week: 'هذا الأسبوع', older: 'أقدم',
    review_title: 'قائمة المراجعة', review_sub: 'راجع المنشورات المولّدة قبل نشرها على حسابات جسور',
    run_scrape: 'سحب الأخبار الآن', new_post: 'منشور من فكرة', search: 'بحث في المنشورات…',
    scrape_running: 'جارٍ سحب الأخبار وتوليد المنشورات…', no_drafts: 'لا توجد منشورات في هذه القائمة',
    last_run: 'آخر تشغيل', slides: 'شرائح', source: 'المصدر', manual: 'يدوي', calendar_origin: 'من التقويم',
    save: 'حفظ', cancel: 'إلغاء', delete: 'حذف', edit: 'تعديل', add: 'إضافة', close: 'إغلاق', back: 'رجوع',
    confirm_delete: 'هل أنت متأكد من الحذف؟ لا يمكن التراجع.', saved: 'تم الحفظ', error: 'حدث خطأ',
    approve: 'اعتماد', reject: 'رفض', restore: 'إعادة للمراجعة', publish: 'نشر', schedule: 'جدولة',
    unschedule: 'إلغاء الجدولة', download: 'تنزيل الصور والنص', regenerate: 'إعادة توليد',
    regenerate_all: 'إعادة توليد المنشور بالكامل', rerender: 'إعادة تصميم الصور', new_images: 'صور خلفية جديدة',
    hook: 'العنوان الجذاب', subtitle: 'العنوان الفرعي', caption: 'نص المنشور', hashtags: 'الهاشتاقات',
    first_comment: 'التعليق الأول', cta: 'دعوة للإجراء (CTA)', badge: 'الشارة', campaign: 'الحملة', none: 'بدون',
    qa: 'فحص الجودة', qa_passed: 'جاهز للنشر', qa_failed: 'يحتاج إصلاح', caption_preview: 'النص كما سيُنشر',
    original: 'المقال الأصلي', open_original: 'فتح المصدر', publish_log: 'سجل النشر',
    slide_heading: 'عنوان الشريحة', slide_body: 'نص الشريحة', upload_bg: 'رفع خلفية', apply: 'تطبيق',
    reject_reason: 'سبب الرفض (اختياري)', publish_title: 'نشر المنشور', publish_now: 'نشر الآن',
    publish_later: 'جدولة لوقت لاحق', when: 'الموعد', providers: 'مزوّدو النشر', not_configured: 'غير مُعدّ',
    configured: 'مُعدّ', pick_platform: 'اختر منصة واحدة على الأقل', relevance: 'الصلة',
    sources_title: 'المصادر', sources_sub: 'المواقع وخلاصات RSS التي تُسحب منها الأخبار',
    add_source: 'إضافة مصدر', presets: 'مصادر مقترحة', test: 'اختبار', scrape_now: 'سحب الآن',
    health: 'الحالة', health_healthy: 'سليم', health_failing: 'متعطل', health_unknown: 'لم يُفحص', last_check: 'آخر فحص',
    enabled: 'مفعّل', disabled: 'معطّل', articles: 'مقالات', drafts: 'مسودات', published: 'منشورة',
    name: 'الاسم', kind: 'النوع', website: 'موقع', rss: 'RSS', base_url: 'رابط الموقع', feed_url: 'رابط RSS',
    listing_urls: 'روابط صفحات الأخبار (سطر لكل رابط)', link_pattern: 'نمط روابط المقالات (Regex — اختياري)',
    link_selector: 'محدد CSS للروابط (اختياري)', body_selector: 'محدد CSS لنص المقال (اختياري)',
    category: 'التصنيف', country: 'الدولة', src_language: 'لغة المصدر', priority: 'الأولوية',
    interval: 'الفحص كل (دقيقة)', max_items: 'أقصى عدد مقالات لكل سحب', brand: 'العلامة',
    test_result: 'نتيجة الاختبار', found_links: 'روابط مكتشفة', view_articles: 'المقالات المسحوبة',
    make_draft: 'توليد منشور', calendar_title: 'تقويم المحتوى', calendar_sub: 'خطّط مواضيع المنشورات وتابع المجدول والمنشور',
    add_item: 'إضافة موضوع', topic: 'الموضوع', notes: 'ملاحظات للكاتب', date: 'التاريخ', time: 'الوقت',
    content_type: 'نوع المحتوى', platform: 'المنصة', generate: 'توليد المنشور', open_draft: 'فتح المسودة',
    planned: 'مخطط', generated: 'تم التوليد', scheduled: 'مجدول',
    campaigns_title: 'الحملات', campaigns_sub: 'اجمع المنشورات تحت أهداف تسويقية واضحة', add_campaign: 'حملة جديدة',
    objective: 'الهدف', color: 'اللون', start: 'البداية', end: 'النهاية', view_posts: 'عرض المنشورات',
    brand_title: 'الهوية البصرية', brand_sub: 'الألوان والشعار وصوت العلامة وقنوات النشر', handle: 'الحساب',
    voice: 'صوت العلامة', cta_text: 'نص الدعوة الافتراضي', colors: 'الألوان', logo: 'الشعار',
    upload_logo: 'رفع شعار (PNG شفاف أو SVG)', remove_logo: 'إزالة الشعار', logo_placement: 'مكان الشعار',
    top_left: 'أعلى اليسار', top_right: 'أعلى اليمين', card_style: 'نمط البطاقة', frosted: 'زجاجي',
    solid: 'كحلي', minimal: 'بدون بطاقة', preview: 'معاينة', refresh_preview: 'تحديث المعاينة',
    publishing_channels: 'قنوات النشر', add_brand: 'علامة جديدة', make_default: 'تعيين كافتراضية', default: 'افتراضية',
    buffer_channels: 'قنوات Buffer', load_channels: 'تحميل القنوات', meta_page: 'Facebook Page ID',
    meta_ig: 'Instagram User ID', up_user: 'اسم المستخدم في upload-post', up_fb: 'Facebook Page ID (upload-post)',
    c_navy: 'الأساسي', c_gold: 'الذهبي', c_goldLight: 'ذهبي فاتح', c_cardTitle: 'عنوان البطاقة', c_cardText: 'نص البطاقة',
    keys_title: 'المفاتيح والاتصالات', keys_sub: 'تُحفظ في قاعدة بياناتك ولا تظهر في المتصفح بعد الحفظ',
    ai_engine: 'محرّك الذكاء الاصطناعي', provider: 'المزوّد', anthropic: 'Claude API (Anthropic)',
    openai_compatible: 'AnythingLLM أو خادم متوافق مع OpenAI', api_key: 'المفتاح', base_url: 'رابط الخادم',
    model: 'النموذج', key_set: 'محفوظ', key_missing: 'غير مضبوط', from_env: 'من متغيرات الخادم',
    from_db: 'من اللوحة', remove_key: 'حذف المفتاح', key_hint: 'اترك الحقل فارغًا للإبقاء على المفتاح الحالي',
    stock_photos: 'صور Pexels المجانية', publishers_keys: 'مفاتيح النشر',
    test_connection: 'اختبار الاتصال', connection_ok: 'الاتصال يعمل', connection_failed: 'فشل الاتصال',
    save_first: 'احفظ التغييرات أولًا ثم اختبر',
    settings_title: 'الإعدادات', settings_sub: 'إعدادات التوليد والجدولة والنشر', generation: 'توليد المحتوى',
    gen_language: 'لغة المنشورات', tone: 'النبرة', audience: 'الجمهور المستهدف', min_relevance: 'أدنى درجة صلة للقبول (0-10)',
    content_slides: 'عدد شرائح المحتوى', image_source: 'مصدر الصور', img_auto: 'تلقائي (صور مجانية ثم صورة المقال)',
    img_source: 'صورة المقال فقط', img_pexels: 'صور Pexels المجانية فقط', credit_source: 'ذكر المصدر في المنشور والصور',
    scheduler: 'الجدولة التلقائية', scrape_enabled: 'تشغيل السحب التلقائي', max_age: 'تجاهل المقالات الأقدم من (أيام)',
    max_drafts: 'أقصى عدد منشورات لكل دورة', publishing: 'النشر', default_provider: 'المزوّد الافتراضي',
    default_platforms: 'المنصات الافتراضية', first_comment_enabled: 'نشر التعليق الأول', buffer_mode: 'طريقة Buffer',
    share_now: 'نشر فوري', add_queue: 'إضافة لطابور Buffer', system: 'حالة النظام', ai: 'الذكاء الاصطناعي', ai_compatible: 'AnythingLLM (متوافق مع OpenAI)',
    storage: 'تخزين الصور', public_ok: 'روابط عامة جاهزة', public_missing: 'الصور غير متاحة للعامة — النشر لن يعمل',
    check: 'فحص الاتصال', connected: 'متصل', disconnected: 'غير متصل', jobs: 'المهام الخلفية',
    stats_title: 'الإحصاءات', stats_sub: 'أداء خط الإنتاج خلال آخر 30 يومًا', collected: 'مقالات مسحوبة',
    approval_rate: 'نسبة القبول', by_source: 'المنشورات حسب المصدر', by_platform: 'النشر حسب المنصة',
    success: 'نجح', failed: 'فشل', by_status: 'المنشورات حسب الحالة',
    login_title: 'تسجيل الدخول', email: 'البريد الإلكتروني', password: 'كلمة المرور', sign_in: 'دخول',
    local_mode: 'وضع التطوير المحلي — بدون تسجيل دخول',
    manual_title: 'منشور جديد من فكرة', manual_hint: 'اكتب الفكرة وسيكتب الذكاء الاصطناعي المنشور ويصمّم الشرائح',
    started: 'بدأت العملية، ستظهر النتائج خلال دقائق', loading: 'جارٍ التحميل…',
  },
  en: {
    appName: 'Jusoor AutoPost', appSub: 'Automated content studio',
    nav_review: 'Review queue', nav_sources: 'Sources', nav_calendar: 'Calendar', nav_campaigns: 'Campaigns',
    nav_brand: 'Brand identity', nav_stats: 'Analytics', nav_settings: 'Settings',
    logout: 'Sign out', language: 'العربية', theme: 'Theme',
    st_all: 'All', st_generating: 'Generating', st_pending_review: 'Pending review', st_approved: 'Ready',
    st_scheduled: 'Scheduled', st_publishing: 'Publishing', st_published: 'Published', st_failed: 'Failed', st_rejected: 'Rejected',
    today: 'Today', yesterday: 'Yesterday', week: 'This week', older: 'Older',
    review_title: 'Review queue', review_sub: 'Review generated posts before they go live',
    run_scrape: 'Fetch news now', new_post: 'Post from an idea', search: 'Search posts…',
    scrape_running: 'Fetching news and generating posts…', no_drafts: 'Nothing here yet',
    last_run: 'Last run', slides: 'slides', source: 'Source', manual: 'Manual', calendar_origin: 'From calendar',
    save: 'Save', cancel: 'Cancel', delete: 'Delete', edit: 'Edit', add: 'Add', close: 'Close', back: 'Back',
    confirm_delete: 'Delete permanently? This cannot be undone.', saved: 'Saved', error: 'Something went wrong',
    approve: 'Approve', reject: 'Reject', restore: 'Back to review', publish: 'Publish', schedule: 'Schedule',
    unschedule: 'Unschedule', download: 'Download images & text', regenerate: 'Regenerate',
    regenerate_all: 'Regenerate whole post', rerender: 'Re-render images', new_images: 'New background photos',
    hook: 'Hook', subtitle: 'Subtitle', caption: 'Caption', hashtags: 'Hashtags', first_comment: 'First comment',
    cta: 'Call to action', badge: 'Badge', campaign: 'Campaign', none: 'None',
    qa: 'Quality checks', qa_passed: 'Ready to publish', qa_failed: 'Needs fixes', caption_preview: 'Final caption',
    original: 'Original article', open_original: 'Open source', publish_log: 'Publish log',
    slide_heading: 'Slide heading', slide_body: 'Slide text', upload_bg: 'Upload background', apply: 'Apply',
    reject_reason: 'Reason (optional)', publish_title: 'Publish post', publish_now: 'Publish now',
    publish_later: 'Schedule for later', when: 'When', providers: 'Publishing providers', not_configured: 'Not configured',
    configured: 'Configured', pick_platform: 'Pick at least one platform', relevance: 'Relevance',
    sources_title: 'Sources', sources_sub: 'Websites and RSS feeds to collect news from',
    add_source: 'Add source', presets: 'Suggested sources', test: 'Test', scrape_now: 'Fetch now',
    health: 'Health', health_healthy: 'Healthy', health_failing: 'Failing', health_unknown: 'Not checked', last_check: 'Last check',
    enabled: 'Enabled', disabled: 'Disabled', articles: 'articles', drafts: 'drafts', published: 'published',
    name: 'Name', kind: 'Type', website: 'Website', rss: 'RSS', base_url: 'Website URL', feed_url: 'RSS URL',
    listing_urls: 'News listing URLs (one per line)', link_pattern: 'Article URL pattern (regex, optional)',
    link_selector: 'Link CSS selector (optional)', body_selector: 'Article body CSS selector (optional)',
    category: 'Category', country: 'Country', src_language: 'Source language', priority: 'Priority',
    interval: 'Check every (minutes)', max_items: 'Max articles per fetch', brand: 'Brand',
    test_result: 'Test result', found_links: 'Links found', view_articles: 'Collected articles',
    make_draft: 'Generate post', calendar_title: 'Content calendar', calendar_sub: 'Plan topics and track scheduled posts',
    add_item: 'Add topic', topic: 'Topic', notes: 'Notes for the writer', date: 'Date', time: 'Time',
    content_type: 'Content type', platform: 'Platform', generate: 'Generate post', open_draft: 'Open draft',
    planned: 'Planned', generated: 'Generated', scheduled: 'Scheduled',
    campaigns_title: 'Campaigns', campaigns_sub: 'Group posts under clear marketing goals', add_campaign: 'New campaign',
    objective: 'Objective', color: 'Colour', start: 'Start', end: 'End', view_posts: 'View posts',
    brand_title: 'Brand identity', brand_sub: 'Colours, logo, voice and publishing channels', handle: 'Handle',
    voice: 'Brand voice', cta_text: 'Default CTA', colors: 'Colours', logo: 'Logo',
    upload_logo: 'Upload logo (transparent PNG or SVG)', remove_logo: 'Remove logo', logo_placement: 'Logo position',
    top_left: 'Top left', top_right: 'Top right', card_style: 'Card style', frosted: 'Frosted',
    solid: 'Navy', minimal: 'No card', preview: 'Preview', refresh_preview: 'Refresh preview',
    publishing_channels: 'Publishing channels', add_brand: 'New brand', make_default: 'Make default', default: 'Default',
    buffer_channels: 'Buffer channels', load_channels: 'Load channels', meta_page: 'Facebook Page ID',
    meta_ig: 'Instagram User ID', up_user: 'upload-post username', up_fb: 'Facebook Page ID (upload-post)',
    c_navy: 'Primary', c_gold: 'Gold', c_goldLight: 'Light gold', c_cardTitle: 'Card title', c_cardText: 'Card text',
    keys_title: 'Keys & connections', keys_sub: 'Stored in your own database; never sent back to the browser',
    ai_engine: 'AI engine', provider: 'Provider', anthropic: 'Claude API (Anthropic)',
    openai_compatible: 'AnythingLLM / OpenAI-compatible server', api_key: 'API key', base_url: 'Server URL',
    model: 'Model', key_set: 'Saved', key_missing: 'Not set', from_env: 'from server variables',
    from_db: 'from dashboard', remove_key: 'Remove key', key_hint: 'Leave empty to keep the current key',
    stock_photos: 'Pexels stock photos', publishers_keys: 'Publishing keys',
    test_connection: 'Test connection', connection_ok: 'Connection works', connection_failed: 'Connection failed',
    save_first: 'Save your changes first, then test',
    settings_title: 'Settings', settings_sub: 'Generation, scheduling and publishing', generation: 'Content generation',
    gen_language: 'Post language', tone: 'Tone', audience: 'Target audience', min_relevance: 'Minimum relevance (0-10)',
    content_slides: 'Content slides', image_source: 'Image source', img_auto: 'Auto (free stock, then article image)',
    img_source: 'Article image only', img_pexels: 'Pexels stock only', credit_source: 'Credit the source',
    scheduler: 'Automation', scrape_enabled: 'Automatic fetching', max_age: 'Ignore articles older than (days)',
    max_drafts: 'Max posts per cycle', publishing: 'Publishing', default_provider: 'Default provider',
    default_platforms: 'Default platforms', first_comment_enabled: 'Post first comment', buffer_mode: 'Buffer mode',
    share_now: 'Share now', add_queue: 'Add to Buffer queue', system: 'System status', ai: 'AI', ai_compatible: 'AnythingLLM (OpenAI-compatible)',
    storage: 'Image storage', public_ok: 'Public URLs ready', public_missing: 'Images are not public — publishing will fail',
    check: 'Test connection', connected: 'Connected', disconnected: 'Not connected', jobs: 'Background jobs',
    stats_title: 'Analytics', stats_sub: 'Pipeline performance over the last 30 days', collected: 'Articles collected',
    approval_rate: 'Approval rate', by_source: 'Posts by source', by_platform: 'Publishing by platform',
    success: 'Success', failed: 'Failed', by_status: 'Posts by status',
    login_title: 'Sign in', email: 'Email', password: 'Password', sign_in: 'Sign in',
    local_mode: 'Local development mode — no sign-in',
    manual_title: 'New post from an idea', manual_hint: 'Describe the idea; AI writes the post and designs the slides',
    started: 'Started — results will appear in a few minutes', loading: 'Loading…',
  },
};

const I18nContext = createContext(null);

function stored(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => stored('ui-lang', 'ar'));
  const [theme, setTheme] = useState(() => stored('ui-theme', 'auto'));

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr';
    document.title = dict[lang].appName;
    try { localStorage.setItem('ui-lang', lang); } catch { /* ignore */ }
  }, [lang]);

  useEffect(() => {
    if (theme === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    try { localStorage.setItem('ui-theme', theme); } catch { /* ignore */ }
  }, [theme]);

  const t = (key) => dict[lang][key] ?? dict.ar[key] ?? key;
  return (
    <I18nContext.Provider value={{ lang, setLang, t, theme, setTheme }}>
      {children}
    </I18nContext.Provider>
  );
}

export const useI18n = () => useContext(I18nContext);
