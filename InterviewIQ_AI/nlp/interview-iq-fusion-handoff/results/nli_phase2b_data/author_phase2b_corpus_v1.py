"""Create and validate the CP-008 Phase 2B candidate NLI corpus.

Data authoring only: this script imports no ML library, loads no model, runs no
inference, and cannot train or create an adapter.  It produces AI-authored
candidates that remain blocked from training until two independent human
reviewers complete the external review ledger.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


AUTHORING_TIMESTAMP = "2026-08-23T19:35:21+03:00"
REFDOC_SHA256 = "BA062768EB02C6DBE16D90024C30B075AF98F85D08B9E946BB26862AAB250F07"
CP005_SHA256 = "5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18"
SPEC_SHA256 = "1B8ED30FA4521F6824B321981968E597246924178DF7F7348D7E735036BAD228"
POLICY_SHA256 = "5AB2584E8241A7D78351E55D2EED777ABB23702208EDA2DDA85B6E47FF95C112"

PROTECTED_CP005_QUESTION_IDS = {
    "CS-001", "CS-005", "DA-001", "DA-017", "DS-001",
    "DS-003", "SE-010", "SE-014", "SE-034", "SE-039",
}
ADDITIONAL_EVALUATION_EXCLUSIONS = {"DS-014"}
ALL_EXCLUDED_QUESTION_IDS = PROTECTED_CP005_QUESTION_IDS | ADDITIONAL_EVALUATION_EXCLUSIONS
TRACK_TARGETS = {"DA": 13, "DS": 13, "CS": 12, "SE": 12}
TRACK_TO_DOMAIN = {
    "DA": "data_analysis",
    "DS": "data_science",
    "CS": "cybersecurity",
    "SE": "software_engineering",
}

ENGLISH_SUMMARY = {
    "DA-002": "A data-analysis process starts by defining the business problem that guides the analysis.",
    "DA-003": "A data analyst examines historical data and produces reports and dashboards for decision support.",
    "DA-004": "Data cleaning detects and corrects or removes inaccurate, incomplete, or inconsistent data.",
    "DA-005": "Handling missing values starts by understanding why the values are missing and how the missingness is distributed.",
    "DA-006": "Outliers are observations that lie unusually far from the rest of the dataset.",
    "DA-007": "The arithmetic mean equals the sum of the values divided by their count.",
    "DA-008": "Standard deviation measures how dispersed values are around their arithmetic mean.",
    "DA-009": "Correlation describes a statistical relationship in which two variables change together.",
    "DA-010": "Pearson correlation measures the strength and direction of a linear relationship between two numeric variables.",
    "DA-011": "Data visualization represents data with charts and plots to make findings easier to understand and communicate.",
    "DA-012": "A bar chart compares values across discrete categories using separated bars.",
    "DA-013": "A box plot summarizes the distribution of a numeric variable through the five-number summary.",
    "DA-014": "A pivot table interactively reorganizes and aggregates data without changing the original data.",
    "DS-002": "In reinforcement learning, an agent interacts with an environment and learns from the outcomes of its actions.",
    "DS-004": "Linear regression models a linear relationship between a numeric dependent variable and one or more predictors.",
    "DS-005": "Logistic regression predicts class membership probabilities and is commonly used for binary classification.",
    "DS-006": "A decision tree predicts by splitting data through a sequence of conditional questions about feature values.",
    "DS-007": "A random forest combines predictions from many decision trees to reach a final prediction.",
    "DS-008": "K-nearest neighbors predicts a new example from the classes of its nearest K neighbors.",
    "DS-009": "K-Means is an unsupervised clustering algorithm that partitions data into a predefined number of clusters.",
    "DS-010": "The elbow method selects K where the improvement in inertia or WCSS begins to slow markedly.",
    "DS-011": "An SVM searches for a separating hyperplane with the largest possible margin between classes.",
    "DS-012": "Naive Bayes is a probabilistic classifier that applies Bayes' theorem to estimate class probabilities.",
    "DS-013": "Gradient descent reduces a loss function by updating parameters opposite to the gradient direction.",
    "DS-015": "Batch gradient descent computes each gradient update using the complete training set.",
    "DS-016": "Bias is error caused by simplifying model assumptions that miss real patterns in the data.",
    "CS-002": "A vulnerability is a weakness in a system, application, or process that can be exploited.",
    "CS-003": "A firewall permits or blocks inbound and outbound network traffic according to predefined security rules.",
    "CS-004": "An IDS detects suspicious activity and raises alerts without actively blocking that activity.",
    "CS-006": "AES is a symmetric encryption algorithm standardized by NIST in 2001.",
    "CS-007": "RSA is an asymmetric encryption algorithm named after Rivest, Shamir, and Adleman.",
    "CS-008": "Hashing converts an input of arbitrary length into a fixed-length digest.",
    "CS-009": "A salt is a unique random value added to a password before hashing it for storage.",
    "CS-010": "TLS encrypts client-server communication and is the modern successor to the deprecated SSL protocol.",
    "CS-011": "A VPN creates an encrypted tunnel between a user device and a VPN server over a public network.",
    "CS-012": "Phishing impersonates a trusted party to trick a victim into revealing sensitive information.",
    "CS-013": "SQL injection sends malicious SQL through application input so that it executes against the database.",
    "CS-014": "Cross-site scripting injects malicious code, usually JavaScript, into a trusted site's browser context.",
    "SE-001": "Object-oriented programming organizes code into objects that combine data with related behavior.",
    "SE-002": "Encapsulation groups data and its operations in a class while restricting direct access to the data.",
    "SE-003": "Inheritance lets a child class acquire properties and methods from a parent class.",
    "SE-004": "Polymorphism lets objects of different classes respond differently to the same call.",
    "SE-005": "An abstract class cannot be instantiated directly and may contain both abstract and implemented methods.",
    "SE-006": "SOLID names five object-oriented design principles intended to improve maintainability and extensibility.",
    "SE-007": "Design patterns are reusable solutions to common software-design problems.",
    "SE-008": "The Singleton pattern ensures one class instance and provides a global access point to it.",
    "SE-009": "MVC separates an application into Model, View, and Controller components.",
    "SE-011": "HTTP GET retrieves data without changing server state.",
    "SE-012": "HTTP status codes are three-digit numbers grouped into five families by their first digit.",
    "SE-013": "SQL databases store data in relational tables governed by a predefined schema.",
}

# Each replacement is applied to the canonical first chunk.  The first ten
# selected documents use three rules; all remaining documents use two, yielding
# exactly 110 near-neighbor contradictions.
NEAR_REPLACEMENTS = {
    "DA-002": [("تبدأ", "تنتهي"), ("تحديد المشكلة", "تجاهل المشكلة"), ("يوجه التحليل بأكمله", "لا يؤثر في التحليل")],
    "DA-003": [("يركز الـ Data Analyst على تحليل البيانات التاريخية", "يركز الـ Data Analyst على بناء نماذج تنبؤية بدل تحليل البيانات التاريخية"), ("البيانات التاريخية", "البيانات المستقبلية فقط"), ("إنتاج تقارير و Dashboards", "تدريب نماذج Deep Learning فقط")],
    "DA-004": [("اكتشاف وتصحيح أو إزالة", "إضافة وتكرار"), ("غير الدقيقة", "الدقيقة فقط"), ("Data Cleaning", "Data Visualization")],
    "DA-005": [("فهم سبب فقدانها", "حذفها فورًا دون فهم السبب"), ("يؤثر ذلك على اختيار", "لا يؤثر ذلك على اختيار"), ("الخطوة الأولى", "الخطوة غير الضرورية")],
    "DA-006": [("تبعد بشكل غير معتاد عن بقية القيم", "تطابق بقية القيم تمامًا"), ("القيم المتطرفة", "القيم المركزية"), ("Outliers", "Missing Values")],
    "DA-007": [("المتوسط الحسابي Mean", "الوسيط Median"), ("مجموع القيم مقسومًا على عددها", "القيمة الأكثر تكرارًا"), ("يدخل في حسابه كل قيمة", "لا يعتمد على أي قيمة")],
    "DA-008": [("الانحراف المعياري Standard Deviation", "المتوسط الحسابي Mean"), ("مدى تشتت القيم", "عدد الفئات"), ("حول متوسطها الحسابي", "حول اسم المتغير")],
    "DA-009": [("الارتباط Correlation يعني وجود علاقة إحصائية", "الارتباط Correlation يثبت وجود علاقة سببية مؤكدة"), ("علاقة إحصائية", "علاقة سببية مؤكدة"), ("يتغيران معًا", "لا يتغير أي منهما")],
    "DA-010": [("قوة واتجاه العلاقة الخطية", "سبب العلاقة غير الخطية"), ("متغيرين رقميين", "متغير نصي واحد"), ("Pearson", "K-Means")],
    "DA-011": [("تمثيل البيانات بصريًا", "حذف البيانات نهائيًا"), ("رسوم بيانية ومخططات", "جداول غير مرئية"), ("تسهيل فهمها", "منع فهمها")],
    "DA-012": [("Bar Chart", "Histogram"), ("فئات منفصلة", "متغير مستمر")],
    "DA-013": [("الـ Box Plot أو Box-and-Whisker Plot", "الـ Pie Chart"), ("الملخص الخماسي", "المتوسط فقط")],
    "DA-014": [("تعيد تنظيم البيانات وتجميعها حسب أبعاد يختارها المستخدم دون تعديل البيانات الأصلية", "تحذف البيانات الأصلية بدل إعادة تنظيمها"), ("دون تعديل البيانات الأصلية", "مع تعديل البيانات الأصلية دائمًا")],
    "DS-002": [("التعلم المعزز Reinforcement Learning", "التعلم غير الموجه Unsupervised Learning"), ("يتفاعل فيه وكيل", "لا يتفاعل فيه أي وكيل")],
    "DS-004": [("متغير تابع رقمي", "فئة نصية فقط"), ("بعلاقة خطية", "بعلاقة عشوائية بلا نموذج")],
    "DS-005": [("التصنيف الثنائي Binary Classification", "التجميع غير الموجه Unsupervised Clustering"), ("احتمالية انتماء المثال إلى فئة", "قيمة مستمرة بلا احتمالات")],
    "DS-006": [("سلسلة من الأسئلة الشرطية", "مسافة واحدة بين الجيران"), ("Decision Tree", "Linear Regression")],
    "DS-007": [("عددًا كبيرًا من أشجار القرار", "شجرة قرار واحدة فقط"), ("يجمع تنبؤاتها", "يتجاهل كل تنبؤاتها")],
    "DS-008": [("أقرب K جيران", "أبعد K جيران"), ("KNN", "K-Means")],
    "DS-009": [("التجميع غير الموجه", "التصنيف الموجه"), ("عدد K من المجموعات", "مجموعة واحدة ثابتة دائمًا")],
    "DS-010": [("طريقة الكوع Elbow Method", "طريقة Confusion Matrix"), ("يتباطأ عندها التحسن", "يزداد عندها الخطأ بلا توقف")],
    "DS-011": [("أكبر هامش Margin", "أصغر هامش Margin"), ("يفصل الفئات", "يدمج جميع الفئات")],
    "DS-012": [("Naive Bayes مصنف احتمالي يعتمد", "Naive Bayes خوارزمية تجميع حتمية تعتمد"), ("نظرية Bayes", "خوارزمية K-Means")],
    "DS-013": [("تقلل دالة الخسارة", "تزيد دالة الخسارة"), ("الاتجاه المعاكس للمشتقة", "نفس اتجاه المشتقة")],
    "DS-015": [("مجموعة التدريب كاملة", "عينة واحدة فقط"), ("قبل كل تحديث واحد", "من دون أي تحديث")],
    "DS-016": [("خطأ ناتج عن افتراضات مبسطة في النموذج", "خطأ ناتج عن ضوضاء القياس فقط"), ("يعجز عن التقاط الأنماط", "يحفظ كل ضوضاء التدريب")],
    "CS-002": [("الثغرة Vulnerability هي", "التهديد Threat هو"), ("ضعف أو خلل", "إجراء حماية مكتمل")],
    "CS-003": [("يسمح بها أو يمنعها", "يسمح بكل الحركة دائمًا"), ("وفق قواعد أمنية", "من دون أي قواعد")],
    "CS-004": [("IDS", "IPS"), ("دون التدخل لمنعها", "ويمنعها تلقائيًا")],
    "CS-006": [("تشفير متماثل", "تشفير غير متماثل"), ("AES", "RSA")],
    "CS-007": [("تشفير غير متماثل", "تشفير متماثل"), ("RSA", "AES")],
    "CS-008": [("ثابتة الطول", "متغيرة الطول وقابلة للعكس"), ("Hashing", "Encryption")],
    "CS-009": [("قيمة عشوائية فريدة", "قيمة ثابتة مشتركة"), ("قبل تمريرها", "بعد حذف كلمة المرور")],
    "CS-010": [("يشفر الاتصال", "يرسل الاتصال من دون تشفير"), ("TLS هو الخليفة الحديث", "SSL هو الخليفة الحديث لـ TLS")],
    "CS-011": [("نفقًا مشفرًا Encrypted Tunnel", "قناة مكشوفة بلا تشفير"), ("VPN", "Firewall")],
    "CS-012": [("التصيد الاحتيالي Phishing هجوم هندسة اجتماعية", "التصيد الاحتيالي Phishing خوارزمية تشفير متماثل"), ("جهة موثوقة", "نظام تشغيل محلي")],
    "CS-013": [("أوامر SQL خبيثة", "أكواد CSS آمنة"), ("قاعدة البيانات", "ملف صورة فقط")],
    "CS-014": [("كودًا برمجيًا خبيثًا عادة JavaScript", "أوامر SQL داخل قاعدة البيانات فقط"), ("متصفح الضحية", "خادم DNS فقط")],
    "SE-001": [("كائنات Objects", "دوال منفصلة بلا كائنات"), ("البيانات والسلوك المرتبط بها", "البيانات فقط دون سلوك")],
    "SE-002": [("تقييد الوصول المباشر", "إتاحة الوصول المباشر دائمًا"), ("Encapsulation", "Inheritance")],
    "SE-003": [("صنف فرعي Child Class", "كائن مستقل بلا صنف أب"), ("اكتساب خصائص ودوال", "حذف خصائص ودوال")],
    "SE-004": [("الاستجابة لنفس الاستدعاء بطرق مختلفة", "الاستجابة باستدعاءات مختلفة بالطريقة نفسها"), ("Polymorphism", "Encapsulation")],
    "SE-005": [("لا يمكن إنشاء كائن مباشر منه", "يجب إنشاء كائن مباشر منه دائمًا"), ("دوال مجردة بلا تنفيذ", "دوال منفذة فقط ولا يقبل التجريد")],
    "SE-006": [("خمسة مبادئ", "مبدأين فقط"), ("أسهل في الصيانة والتوسعة", "أصعب في الصيانة والتوسعة")],
    "SE-007": [("حلول قابلة لإعادة الاستخدام", "نسخ كود مخصصة لا يعاد استخدامها"), ("مشكلات تصميم برمجي شائعة", "أخطاء تشغيل عشوائية فقط")],
    "SE-008": [("نسخة واحدة فقط", "عدد غير محدود من النسخ"), ("نقطة وصول عامة", "منع أي وصول")],
    "SE-009": [("يقسم التطبيق إلى ثلاثة مكونات هي النموذج Model والعرض View والمتحكم Controller", "يجمع التطبيق في مكون واحد فقط"), ("فصل الاهتمامات Separation of Concerns", "دمج كل الاهتمامات")],
    "SE-011": [("دون إحداث تغيير في حالته", "مع تغيير حالة الخادم دائمًا"), ("استرجاع البيانات", "حذف البيانات")],
    "SE-012": [("ثلاث خانات", "خانتين فقط"), ("خمس عائلات", "عائلة واحدة")],
    "SE-013": [("ذات مخطط Schema صارم", "دون مخطط Schema"), ("تخزن البيانات في جداول", "تخزن البيانات كصور فقط")],
}

TRANSLITERATION_REPLACEMENTS = [
    ("Reinforcement Learning", "رينفورسمنت ليرننج"), ("Unsupervised Learning", "أنسوبرفايزد ليرننج"),
    ("Standard Deviation", "ستاندرد ديفييشن"), ("Linear Regression", "لينير ريجريشن"),
    ("Logistic Regression", "لوجستك ريجريشن"), ("Binary Classification", "باينري كلاسيفيكيشن"),
    ("Decision Tree", "ديسيجن تري"), ("Random Forest", "راندوم فورست"),
    ("Gradient Descent", "جراديانت ديسنت"), ("Data Visualization", "داتا فيجوالايزيشن"),
    ("Data Cleaning", "داتا كليننج"), ("Data Analyst", "داتا أناليست"),
    ("Data Scientist", "داتا ساينتست"), ("Missing Values", "ميسنج فاليوز"),
    ("Box-and-Whisker Plot", "بوكس أند ويسكر بلوت"), ("Five-Number Summary", "فايف نمبر سامري"),
    ("Separation of Concerns", "سيباريشن أوف كونسيرنز"), ("Cross-Site Scripting", "كروس سايت سكربتنج"),
    ("Encrypted Tunnel", "إنكريبتد تانل"), ("Support Vector Machine", "سابورت فيكتور ماشين"),
    ("Business Question", "بزنس كويستشن"), ("Relational Databases", "ريليشنال داتابيزز"),
    ("Computer Vision", "كمبيوتر فيجن"), ("Design Patterns", "ديزاين باترنز"),
    ("Abstract Class", "أبستراكت كلاس"), ("Child Class", "تشايلد كلاس"),
    ("Parent Class", "بارنت كلاس"), ("HTTP Status Codes", "إتش تي تي بي ستاتس كودز"),
    ("SQL Injection", "إس كيو إل إنجكشن"), ("JavaScript", "جافاسكربت"),
    ("Dashboard", "داشبورد"), ("Dashboards", "داشبوردز"),
    ("Outliers", "أوتلايرز"), ("Correlation", "كوريليشن"),
    ("Causation", "كوزيشن"), ("Pearson", "بيرسون"),
    ("Bar Chart", "بار تشارت"), ("Histogram", "هيستوجرام"),
    ("Box Plot", "بوكس بلوت"), ("Pivot Table", "بيفوت تيبل"),
    ("Agent", "إيجنت"), ("Environment", "إنفايرونمنت"),
    ("Features", "فيتشرز"), ("Ensemble", "إنسامبل"),
    ("K-Nearest Neighbors", "كي نييرست نيبرز"), ("K-Means", "كي مينز"),
    ("Clusters", "كلسترز"), ("Elbow Method", "إلبو ميثود"),
    ("Confusion Matrix", "كونفيوجن ماتريكس"), ("Hyperplane", "هايبر بلين"),
    ("Margin", "مارجن"), ("Naive Bayes", "نايف بايز"),
    ("Vulnerability", "فالنرابيليتي"), ("Threat", "ثريت"),
    ("Firewall", "فايروول"), ("Hashing", "هاشينج"),
    ("Encryption", "إنكريبشن"), ("Phishing", "فيشينج"),
    ("Encapsulation", "إنكابسوليشن"), ("Inheritance", "إنهيريتنس"),
    ("Polymorphism", "بوليمورفزم"), ("Singleton", "سينجلتون"),
    ("Schema", "سكيما"), ("Objects", "أوبجكتس"),
    ("Class", "كلاس"), ("Model", "موديل"), ("View", "فيو"),
    ("Controller", "كنترولر"), ("Mean", "مين"), ("Median", "ميديان"),
    ("Mode", "مود"), ("VPN", "في بي إن"), ("IDS", "آي دي إس"),
    ("IPS", "آي بي إس"), ("AES", "إيه إي إس"), ("RSA", "آر إس إيه"),
    ("SSL", "إس إس إل"), ("TLS", "تي إل إس"), ("SQL", "إس كيو إل"),
    ("NoSQL", "نو إس كيو إل"), ("OOP", "أو أو بي"), ("MVC", "إم في سي"),
    ("HTTP", "إتش تي تي بي"), ("NIST", "إن آي إس تي"), ("SVM", "إس في إم"),
    ("KNN", "كي إن إن"), ("WCSS", "دبليو سي إس إس"), ("Inertia", "إنيرشيا"),
]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text)).casefold().replace("ـ", "")
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return " ".join(re.findall(r"\w+", normalized, flags=re.UNICODE))


def token_set(text: str) -> set[str]:
    return set(normalize_text(text).split())


def jaccard(a: str, b: str) -> float:
    left, right = token_set(a), token_set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def transliterate_terms(text: str) -> tuple[str, int]:
    result = text
    changes = 0
    for source, replacement in TRANSLITERATION_REPLACEMENTS:
        if source in result:
            result = result.replace(source, replacement)
            changes += 1
    if changes == 0:
        result = "بصياغة ترانسلِت تقنية: " + result
    return result, changes


def standard_style(global_index: int, slot: int) -> str:
    # Per label: 50 MSA, 50 Egyptian, 60 code-switch, 20 transliteration, 20 English.
    if global_index < 20 and slot == 0:
        return "english_diagnostic"
    if global_index < 20 and slot == 1:
        return "arabic_transliteration_variant"
    if slot == 2:
        return "arabic_english_code_switch"
    if global_index < 10 and slot == 3:
        return "arabic_english_code_switch"
    if 10 <= global_index < 30 and slot == 3:
        return "arabic_msa"
    if global_index >= 30 and slot == 3:
        return "egyptian_arabic"
    if global_index >= 20 and slot == 0:
        return "arabic_msa"
    if global_index >= 20 and slot == 1:
        return "egyptian_arabic"
    raise AssertionError((global_index, slot))


def contradiction_style(global_index: int, slot: int) -> str:
    # English is deliberately assigned only to direct-contradiction slots.
    decade = global_index // 10
    if decade == 0:
        return ("arabic_english_code_switch", "arabic_transliteration_variant", "arabic_english_code_switch", "english_diagnostic")[slot]
    if decade == 1:
        return ("arabic_english_code_switch", "arabic_transliteration_variant", "english_diagnostic", "arabic_msa")[slot]
    if decade == 2:
        return ("arabic_english_code_switch", "arabic_msa", "egyptian_arabic", "arabic_msa")[slot]
    if decade in {3, 4}:
        return ("arabic_english_code_switch", "arabic_msa", "egyptian_arabic", "egyptian_arabic")[slot]
    raise AssertionError((global_index, slot))


def style_entailment(style: str, premise: str, question_id: str, preservation: bool) -> str:
    if style == "english_diagnostic":
        return ENGLISH_SUMMARY[question_id]
    if preservation and style == "arabic_msa":
        return premise
    if style == "arabic_msa":
        return "خلاصة المعنى أن " + premise
    if style == "egyptian_arabic":
        return "المعنى ببساطة إن " + premise
    if style == "arabic_english_code_switch":
        return ("Technically speaking، " if preservation else "In other words، ") + premise
    if style == "arabic_transliteration_variant":
        transformed, _ = transliterate_terms(premise)
        return "بصياغة المصطلحات المنطوقة، " + transformed
    raise ValueError(style)


def style_direct_contradiction(style: str, premise: str, question_id: str) -> str:
    if style == "english_diagnostic":
        return "It is false that " + ENGLISH_SUMMARY[question_id][0].lower() + ENGLISH_SUMMARY[question_id][1:]
    if style == "arabic_msa":
        return "ليس صحيحًا أن " + premise
    if style == "egyptian_arabic":
        return "مش صحيح إن " + premise
    if style == "arabic_english_code_switch":
        return "It is not true that، " + premise
    if style == "arabic_transliteration_variant":
        transformed, _ = transliterate_terms(premise)
        return "مش صحيح إن " + transformed
    raise ValueError(style)


def style_near_contradiction(style: str, mutated: str) -> str:
    if style == "arabic_msa":
        return mutated
    if style == "egyptian_arabic":
        return "الادعاء هنا بيقول إن " + mutated
    if style == "arabic_english_code_switch":
        return "The claim says، " + mutated
    if style == "arabic_transliteration_variant":
        transformed, _ = transliterate_terms(mutated)
        return transformed
    raise ValueError(f"Near-neighbor contradiction cannot use unsupported style {style}")


def style_neutral(style: str, donor_text: str, donor_question_id: str) -> str:
    if style == "english_diagnostic":
        return ENGLISH_SUMMARY[donor_question_id]
    if style == "arabic_msa":
        return "معلومة تقنية مستقلة: " + donor_text
    if style == "egyptian_arabic":
        return "معلومة تانية مستقلة بتقول إن " + donor_text
    if style == "arabic_english_code_switch":
        return "A separate technical fact is، " + donor_text
    if style == "arabic_transliteration_variant":
        transformed, _ = transliterate_terms(donor_text)
        return "معلومة تقنية منفصلة: " + transformed
    raise ValueError(style)


def distribution(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(record[key]) for record in records).items()))


def select_documents(refdocs: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for track in ("DA", "DS", "CS", "SE"):
        eligible = [
            doc for doc in refdocs["documents"]
            if doc["track"] == track and doc["question_id"] not in ALL_EXCLUDED_QUESTION_IDS
        ]
        chosen = eligible[: TRACK_TARGETS[track]]
        if len(chosen) != TRACK_TARGETS[track]:
            raise ValueError(f"Not enough eligible {track} documents")
        for track_index, doc in enumerate(chosen):
            copy = dict(doc)
            copy["_split"] = "train" if track_index < 10 else "dev"
            selected.append(copy)
    if len(selected) != 50:
        raise AssertionError(len(selected))
    return selected


def donor_document(
    selected: list[dict[str, Any]], current: dict[str, Any], difficulty: str, offset: int
) -> dict[str, Any]:
    same_split = [doc for doc in selected if doc["_split"] == current["_split"] and doc["question_id"] != current["question_id"]]
    if difficulty == "semantically_adjacent_neutral":
        pool = [doc for doc in same_split if doc["track"] == current["track"]]
    else:
        pool = [doc for doc in same_split if doc["track"] != current["track"]]
    if not pool:
        raise ValueError(f"No donor pool for {current['question_id']} {difficulty}")
    current_position = next(i for i, doc in enumerate(selected) if doc["question_id"] == current["question_id"])
    return pool[(current_position + offset) % len(pool)]


def build_records(selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    case_number = 1
    for global_index, doc in enumerate(selected):
        qid = doc["question_id"]
        split = doc["_split"]
        chunks = doc["chunks"]
        if len(chunks) < 6:
            raise ValueError(f"{qid} has fewer than six chunks")
        base_source = {
            "question_id": qid,
            "question": doc["question"],
            "reference_corpus_path": "data/refdocs/reference_docs_250_FINAL_v1.json",
            "reference_corpus_sha256": REFDOC_SHA256,
            "authoring_method": "AI_CANDIDATE_FROM_CANONICAL_REFERENCE_PENDING_HUMAN_REVIEW",
            "review_status": "human_review_pending",
        }

        # Four entailments per question.
        for slot in range(4):
            style = standard_style(global_index, slot)
            preservation = global_index < 20 and slot == 3
            difficulty = "domain_entailment_preservation" if preservation else "paraphrase_entailment"
            premise_chunk = chunks[0] if style == "english_diagnostic" else chunks[slot]
            premise = premise_chunk["text"]
            hypothesis = style_entailment(style, premise, qid, preservation)
            source = dict(base_source, reference_id=premise_chunk["chunk_id"], premise_is_key_point=premise_chunk["chunk_id"] in doc["key_points"])
            records.append({
                "case_id": f"NLI-TRAIN-P2B-{case_number:04d}", "question_id": qid,
                "premise": premise, "hypothesis": hypothesis, "label": "entailment",
                "language_style": style, "difficulty_type": difficulty, "source": source,
                "rationale": "The candidate hypothesis preserves the material claim in the canonical premise; two independent human reviewers must confirm scope and dialect fidelity.",
                "split": split, "pair_group_id": f"P2B-{qid}-{premise_chunk['chunk_id']}",
                "semantic_family_ids": [f"question:{qid}"], "technical_domain": TRACK_TO_DOMAIN[doc["track"]],
                "technical_terminology": True,
            })
            case_number += 1

        # Four contradictions per question: 3/1 near/direct for the first ten,
        # 2/2 for the remaining forty.
        near_count = 3 if global_index < 10 else 2
        rules = NEAR_REPLACEMENTS[qid]
        if len(rules) != near_count:
            raise ValueError(f"{qid} needs {near_count} near-neighbor rules, got {len(rules)}")
        first_chunk = chunks[0]
        for slot in range(4):
            style = contradiction_style(global_index, slot)
            if slot < near_count:
                difficulty = "near_neighbor_contradiction"
                old, new = rules[slot]
                if old not in first_chunk["text"]:
                    raise ValueError(f"Near-neighbor source phrase {old!r} absent from {qid} first chunk")
                premise_chunk = first_chunk
                hypothesis = style_near_contradiction(style, first_chunk["text"].replace(old, new, 1))
                rationale = f"The candidate replaces {old!r} with {new!r}, changing a material technical relation; human reviewers must confirm the contradiction is explicit rather than merely neutral."
            else:
                difficulty = "direct_contradiction"
                premise_chunk = chunks[min(slot + 1, len(chunks) - 1)]
                if style == "english_diagnostic":
                    premise_chunk = first_chunk
                hypothesis = style_direct_contradiction(style, premise_chunk["text"], qid)
                rationale = "The candidate explicitly negates the canonical premise; human reviewers must confirm there is no scope or modality ambiguity."
            source = dict(base_source, reference_id=premise_chunk["chunk_id"], premise_is_key_point=premise_chunk["chunk_id"] in doc["key_points"])
            records.append({
                "case_id": f"NLI-TRAIN-P2B-{case_number:04d}", "question_id": qid,
                "premise": premise_chunk["text"], "hypothesis": hypothesis, "label": "contradiction",
                "language_style": style, "difficulty_type": difficulty, "source": source,
                "rationale": rationale, "split": split,
                "pair_group_id": f"P2B-{qid}-{premise_chunk['chunk_id']}",
                "semantic_family_ids": [f"question:{qid}"], "technical_domain": TRACK_TO_DOMAIN[doc["track"]],
                "technical_terminology": True,
            })
            case_number += 1

        # Four neutral cases per question.  Donors always stay inside the same
        # split so their semantic family cannot bridge train and dev.
        technical_count = 3 if global_index < 20 else 2
        for slot in range(4):
            style = standard_style(global_index, slot)
            difficulty = "neutral_technical" if slot < technical_count else "semantically_adjacent_neutral"
            premise_chunk = chunks[(slot + 2) % len(chunks)]
            donor = donor_document(selected, doc, difficulty, slot)
            donor_chunk = donor["chunks"][0] if style == "english_diagnostic" else donor["chunks"][(slot + 1) % len(donor["chunks"])]
            hypothesis = style_neutral(style, donor_chunk["text"], donor["question_id"])
            source = dict(
                base_source,
                reference_id=premise_chunk["chunk_id"],
                premise_is_key_point=premise_chunk["chunk_id"] in doc["key_points"],
                hypothesis_source_question_id=donor["question_id"],
                hypothesis_source_reference_id=donor_chunk["chunk_id"],
            )
            records.append({
                "case_id": f"NLI-TRAIN-P2B-{case_number:04d}", "question_id": qid,
                "premise": premise_chunk["text"], "hypothesis": hypothesis, "label": "neutral",
                "language_style": style, "difficulty_type": difficulty, "source": source,
                "rationale": f"The hypothesis comes from independent approved source question {donor['question_id']} and is not resolved by the current premise; human reviewers must confirm neutrality, especially for adjacent-domain cases.",
                "split": split, "pair_group_id": f"P2B-{qid}-{premise_chunk['chunk_id']}",
                "semantic_family_ids": [f"question:{qid}", f"question:{donor['question_id']}"],
                "technical_domain": TRACK_TO_DOMAIN[doc["track"]], "technical_terminology": True,
            })
            case_number += 1

    if len(records) != 600:
        raise AssertionError(len(records))
    return records


def build_review_ledger(records: list[dict[str, Any]], corpus_sha: str) -> dict[str, Any]:
    entries = []
    for record in records:
        difficulty = record["difficulty_type"]
        if difficulty in {"domain_entailment_preservation", "direct_contradiction"}:
            confidence = "high"
        elif difficulty in {"near_neighbor_contradiction", "semantically_adjacent_neutral"}:
            confidence = "low"
        else:
            confidence = "medium"
        ambiguity = difficulty in {"near_neighbor_contradiction", "semantically_adjacent_neutral"}
        entries.append({
            "case_id": record["case_id"],
            "reviewer_status": "AI_FIRST_PASS_ONLY_HUMAN_REVIEW_REQUIRED",
            "label_confidence": confidence,
            "ambiguity_flag": ambiguity,
            "adjudication_status": "PENDING_TWO_INDEPENDENT_HUMAN_REVIEWS",
            "reviewer_1": None,
            "reviewer_2": None,
            "adjudicator": None,
            "ai_generated": True,
            "accepted_for_training": False,
            "required_action": "Two domain-qualified human reviewers must independently verify premise-hypothesis semantics, language style, difficulty, source independence, and label; disagreements require adjudication.",
        })
    return {
        "schema_version": 1,
        "ledger_id": "interviewiq-nli-phase2b-review-ledger-v1",
        "created_at": AUTHORING_TIMESTAMP,
        "corpus_sha256": corpus_sha,
        "status": "HUMAN_REVIEW_PENDING",
        "minimum_independent_human_reviewers": 2,
        "ai_only_labels_accepted": False,
        "summary": {
            "records": len(entries),
            "human_approved": 0,
            "human_review_pending": len(entries),
            "ambiguity_flagged": sum(bool(entry["ambiguity_flag"]) for entry in entries),
            "accepted_for_training": 0,
        },
        "entries": entries,
    }


def validate_and_summarize(
    records: list[dict[str, Any]], selected: list[dict[str, Any]], cp005: dict[str, Any], refdocs: dict[str, Any]
) -> dict[str, Any]:
    required_fields = {"case_id", "question_id", "premise", "hypothesis", "label", "language_style", "difficulty_type", "source", "rationale"}
    ref_by_qid = {doc["question_id"]: doc for doc in refdocs["documents"]}
    ref_text_by_id = {chunk["chunk_id"]: chunk["text"] for doc in refdocs["documents"] for chunk in doc["chunks"]}

    missing_fields = []
    provenance_errors = []
    for record in records:
        missing = required_fields - record.keys()
        if missing:
            missing_fields.append({"case_id": record.get("case_id"), "missing": sorted(missing)})
        source = record["source"]
        if record["question_id"] != source["question_id"]:
            provenance_errors.append(f"{record['case_id']}: source question mismatch")
        if source["reference_id"] not in ref_text_by_id or ref_text_by_id[source["reference_id"]] != record["premise"]:
            provenance_errors.append(f"{record['case_id']}: premise is not canonical source text")
        if record["question_id"] not in ref_by_qid:
            provenance_errors.append(f"{record['case_id']}: unresolved question")

    ids = [record["case_id"] for record in records]
    pairs = [(normalize_text(record["premise"]), normalize_text(record["hypothesis"])) for record in records]
    duplicate_ids = sorted(key for key, count in Counter(ids).items() if count > 1)
    duplicate_pairs = [pair for pair, count in Counter(pairs).items() if count > 1]

    eval_cases = list(cp005["cases"])
    eval_qids = {case["source_question_id"] for case in eval_cases}
    eval_premises = {normalize_text(case["premise"]) for case in eval_cases}
    eval_hypotheses = {normalize_text(case["hypothesis"]) for case in eval_cases}
    eval_pairs = {(normalize_text(case["premise"]), normalize_text(case["hypothesis"])) for case in eval_cases}
    qid_hits = [record["case_id"] for record in records if record["question_id"] in eval_qids]
    premise_hits = [record["case_id"] for record in records if normalize_text(record["premise"]) in eval_premises]
    hypothesis_hits = [record["case_id"] for record in records if normalize_text(record["hypothesis"]) in eval_hypotheses]
    pair_hits = [record["case_id"] for record in records if (normalize_text(record["premise"]), normalize_text(record["hypothesis"])) in eval_pairs]

    # Conservative semantic-copy heuristic.  Human semantic-family review is
    # still mandatory and remains pending; this only rejects very high lexical
    # similarity to CP-005.
    eval_texts = [case["premise"] for case in eval_cases] + [case["hypothesis"] for case in eval_cases]
    semantic_similarity_hits = []
    maximum_jaccard = 0.0
    for record in records:
        for field in ("premise", "hypothesis"):
            score = max(jaccard(record[field], eval_text) for eval_text in eval_texts)
            maximum_jaccard = max(maximum_jaccard, score)
            if score >= 0.8:
                semantic_similarity_hits.append({"case_id": record["case_id"], "field": field, "max_token_jaccard": round(score, 6)})

    qids_by_split = {
        split: {record["question_id"] for record in records if record["split"] == split}
        for split in ("train", "dev")
    }
    family_splits: dict[str, set[str]] = defaultdict(set)
    for record in records:
        for family in record["semantic_family_ids"]:
            family_splits[family].add(record["split"])
    cross_split_families = sorted(family for family, splits in family_splits.items() if len(splits) > 1)
    group_splits: dict[str, set[str]] = defaultdict(set)
    for record in records:
        group_splits[record["pair_group_id"]].add(record["split"])
    cross_split_groups = sorted(group for group, splits in group_splits.items() if len(splits) > 1)

    expected_label = {"contradiction": 200, "entailment": 200, "neutral": 200}
    expected_language = {
        "arabic_english_code_switch": 180,
        "arabic_msa": 150,
        "arabic_transliteration_variant": 60,
        "egyptian_arabic": 150,
        "english_diagnostic": 60,
    }
    expected_difficulty = {
        "direct_contradiction": 90,
        "domain_entailment_preservation": 20,
        "near_neighbor_contradiction": 110,
        "neutral_technical": 120,
        "paraphrase_entailment": 180,
        "semantically_adjacent_neutral": 80,
    }
    actual_label = distribution(records, "label")
    actual_language = distribution(records, "language_style")
    actual_difficulty = distribution(records, "difficulty_type")
    split_counts = Counter(record["split"] for record in records)
    technical_count = sum(bool(record["technical_terminology"]) for record in records)

    structural_hard_failures = {
        "wrong_total_count": len(records) != 600,
        "label_distribution_mismatch": actual_label != expected_label,
        "language_distribution_mismatch": actual_language != expected_language,
        "difficulty_distribution_mismatch": actual_difficulty != expected_difficulty,
        "train_count_mismatch": split_counts["train"] != 480,
        "dev_count_mismatch": split_counts["dev"] != 120,
        "question_count_mismatch": len({record["question_id"] for record in records}) != 50,
        "technical_minimum_missed": technical_count < 360,
        "missing_required_fields": bool(missing_fields),
        "duplicate_case_ids": bool(duplicate_ids),
        "duplicate_normalized_pairs": bool(duplicate_pairs),
        "provenance_errors": bool(provenance_errors),
        "protected_question_id_hits": bool(qid_hits),
        "evaluation_premise_hits": bool(premise_hits),
        "evaluation_hypothesis_hits": bool(hypothesis_hits),
        "evaluation_pair_hits": bool(pair_hits),
        "high_semantic_similarity_hits": bool(semantic_similarity_hits),
        "train_dev_question_overlap": bool(qids_by_split["train"] & qids_by_split["dev"]),
        "cross_split_semantic_families": bool(cross_split_families),
        "cross_split_pair_groups": bool(cross_split_groups),
    }
    if any(structural_hard_failures.values()):
        raise ValueError(f"Corpus validation failed: {structural_hard_failures}; semantic={semantic_similarity_hits[:5]}")

    return {
        "status": "PARTIAL_PASS_HUMAN_REVIEW_REQUIRED",
        "training_ready": False,
        "structural_and_exact_leakage_checks_passed": True,
        "human_semantic_review_passed": False,
        "counts": {
            "records": len(records),
            "questions": len({record["question_id"] for record in records}),
            "train_records": split_counts["train"],
            "dev_records": split_counts["dev"],
            "train_questions": len(qids_by_split["train"]),
            "dev_questions": len(qids_by_split["dev"]),
            "technical_examples": technical_count,
        },
        "distributions": {
            "label": actual_label,
            "language_style": actual_language,
            "difficulty_type": actual_difficulty,
            "technical_domain": distribution(records, "technical_domain"),
        },
        "leakage": {
            "cp005_dataset_sha256_verified": True,
            "cp005_do_not_train_verified": cp005.get("do_not_train") is True,
            "protected_cp005_question_ids": sorted(PROTECTED_CP005_QUESTION_IDS),
            "additional_evaluation_exclusions": sorted(ADDITIONAL_EVALUATION_EXCLUSIONS),
            "protected_question_id_hits": qid_hits,
            "evaluation_premise_hits": premise_hits,
            "evaluation_hypothesis_hits": hypothesis_hits,
            "evaluation_pair_hits": pair_hits,
            "high_semantic_similarity_hits": semantic_similarity_hits,
            "semantic_similarity_threshold_token_jaccard": 0.8,
            "maximum_observed_token_jaccard": round(maximum_jaccard, 6),
            "manual_semantic_family_gate": "PENDING_TWO_INDEPENDENT_HUMAN_REVIEWS",
        },
        "duplicates": {
            "duplicate_case_ids": duplicate_ids,
            "duplicate_normalized_pair_count": len(duplicate_pairs),
        },
        "split_integrity": {
            "train_question_ids": sorted(qids_by_split["train"]),
            "dev_question_ids": sorted(qids_by_split["dev"]),
            "question_id_overlap": sorted(qids_by_split["train"] & qids_by_split["dev"]),
            "cross_split_semantic_families": cross_split_families,
            "cross_split_pair_groups": cross_split_groups,
        },
        "provenance": {
            "reference_corpus_path": "data/refdocs/reference_docs_250_FINAL_v1.json",
            "reference_corpus_sha256": REFDOC_SHA256,
            "standalone_question_bank_configured_path_present": False,
            "question_and_key_point_source": "reference_docs_250_FINAL_v1.json documents[].question/key_points",
            "unresolved_or_noncanonical_records": provenance_errors,
        },
        "review_gate": {
            "ai_generated_candidates": 600,
            "human_approved": 0,
            "human_review_pending": 600,
            "accepted_for_training": 0,
            "minimum_independent_human_reviewers": 2,
            "adjudication_required_on_disagreement": True,
            "claim_limit": "Structural/exact leakage PASS does not satisfy the mandatory human semantic-family and label review gate.",
        },
    }


def main() -> int:
    nlp_root = Path(__file__).resolve().parents[2]
    refdocs_path = nlp_root / "data/refdocs/reference_docs_250_FINAL_v1.json"
    cp005_path = nlp_root / "data/nli/evaluation/heldout_ar_codeswitch_v1.json"
    spec_path = nlp_root / "data/nli/training/phase2b_lora_corpus_spec_v1.json"
    policy_path = nlp_root / "data/nli/training/cp005_exclusion_policy_v1.json"
    corpus_path = nlp_root / "data/nli/training/phase2b_lora_corpus_v1.json"
    review_path = nlp_root / "data/nli/training/phase2b_lora_review_ledger_v1.json"
    split_path = nlp_root / "data/nli/training/phase2b_lora_split_manifest_v1.json"
    result_dir = nlp_root / "results/nli_phase2b_data"
    validation_path = result_dir / "corpus_preflight_validation_v1.json"
    quality_path = result_dir / "corpus_quality_report_v1.md"

    expected = {
        refdocs_path: REFDOC_SHA256,
        cp005_path: CP005_SHA256,
        spec_path: SPEC_SHA256,
        policy_path: POLICY_SHA256,
    }
    for path, expected_hash in expected.items():
        if sha256_file(path) != expected_hash:
            raise ValueError(f"Frozen dependency hash mismatch: {path}")

    refdocs = read_json(refdocs_path)
    cp005 = read_json(cp005_path)
    if cp005.get("do_not_train") is not True or len(cp005.get("cases", [])) != 45:
        raise ValueError("CP-005 exclusion source is invalid")
    selected = select_documents(refdocs)
    records = build_records(selected)
    validation = validate_and_summarize(records, selected, cp005, refdocs)

    corpus = {
        "schema_version": 1,
        "dataset_id": "interviewiq-nli-phase2b-lora-corpus-v1",
        "version": "1.0.0-draft",
        "created_at": AUTHORING_TIMESTAMP,
        "status": "DRAFT_HUMAN_REVIEW_REQUIRED_NOT_TRAINING_READY",
        "training_authorized": False,
        "human_review_complete": False,
        "corpus_spec_path": "data/nli/training/phase2b_lora_corpus_spec_v1.json",
        "corpus_spec_sha256": SPEC_SHA256,
        "exclusion_policy_path": "data/nli/training/cp005_exclusion_policy_v1.json",
        "exclusion_policy_sha256": POLICY_SHA256,
        "source_corpus_path": "data/refdocs/reference_docs_250_FINAL_v1.json",
        "source_corpus_sha256": REFDOC_SHA256,
        "evaluation_exclusion_path": "data/nli/evaluation/heldout_ar_codeswitch_v1.json",
        "evaluation_exclusion_sha256": CP005_SHA256,
        "authoring_boundary": "AI-authored candidates only; no label is accepted for training until two independent human reviews and adjudication where needed.",
        "records": records,
    }
    write_json(corpus_path, corpus)
    corpus_sha = sha256_file(corpus_path)

    ledger = build_review_ledger(records, corpus_sha)
    write_json(review_path, ledger)
    review_sha = sha256_file(review_path)

    train_records = [record for record in records if record["split"] == "train"]
    dev_records = [record for record in records if record["split"] == "dev"]
    split_manifest = {
        "schema_version": 1,
        "manifest_id": "interviewiq-nli-phase2b-split-manifest-v1",
        "created_at": AUTHORING_TIMESTAMP,
        "status": "FROZEN_SPLIT_HUMAN_REVIEW_PENDING",
        "corpus_path": "data/nli/training/phase2b_lora_corpus_v1.json",
        "corpus_sha256": corpus_sha,
        "review_ledger_path": "data/nli/training/phase2b_lora_review_ledger_v1.json",
        "review_ledger_sha256": review_sha,
        "split_level": "complete_question_id",
        "seed": None,
        "selection_rule": "First ten eligible documents per technical track are train; remaining selected documents are dev. All neutral donor families stay within the receiving split.",
        "train": {
            "record_count": len(train_records),
            "question_ids": sorted({record["question_id"] for record in train_records}),
            "case_ids": [record["case_id"] for record in train_records],
            "label_distribution": distribution(train_records, "label"),
            "language_distribution": distribution(train_records, "language_style"),
            "difficulty_distribution": distribution(train_records, "difficulty_type"),
        },
        "dev": {
            "record_count": len(dev_records),
            "question_ids": sorted({record["question_id"] for record in dev_records}),
            "case_ids": [record["case_id"] for record in dev_records],
            "label_distribution": distribution(dev_records, "label"),
            "language_distribution": distribution(dev_records, "language_style"),
            "difficulty_distribution": distribution(dev_records, "difficulty_type"),
        },
        "integrity": validation["split_integrity"],
        "training_authorized": False,
    }
    write_json(split_path, split_manifest)
    split_sha = sha256_file(split_path)

    validation_artifact = {
        "schema_version": 1,
        "validation_id": "interviewiq-nli-phase2b-corpus-preflight-v1",
        "created_at": AUTHORING_TIMESTAMP,
        **validation,
        "frozen_artifacts": {
            "corpus": {"path": "data/nli/training/phase2b_lora_corpus_v1.json", "sha256": corpus_sha},
            "review_ledger": {"path": "data/nli/training/phase2b_lora_review_ledger_v1.json", "sha256": review_sha},
            "split_manifest": {"path": "data/nli/training/phase2b_lora_split_manifest_v1.json", "sha256": split_sha},
            "source_corpus": {"path": "data/refdocs/reference_docs_250_FINAL_v1.json", "sha256": REFDOC_SHA256},
            "cp005_exclusion_source": {"path": "data/nli/evaluation/heldout_ar_codeswitch_v1.json", "sha256": CP005_SHA256},
        },
        "no_model_or_training_actions": {
            "nli_model_loaded": False,
            "inference_run": False,
            "lora_training_run": False,
            "adapter_checkpoint_created": False,
            "production_behavior_changed": False,
        },
    }
    write_json(validation_path, validation_artifact)
    validation_sha = sha256_file(validation_path)

    quality = f"""# CP-008 Phase 2B Corpus Quality Report

- Result: `PARTIAL PASS — STRUCTURE/EXACT LEAKAGE PASS; HUMAN REVIEW REQUIRED`.
- Candidate records: `600`; train `480`; dev `120`; complete question IDs `50` (`40/10`).
- Training-ready records: `0`. All 600 records are AI-authored candidates pending two independent human reviews and adjudication where required.
- No NLI model was loaded; no inference or training ran; no adapter checkpoint or production change exists.

## Distribution

| Dimension | Counts |
|---|---|
| Labels | entailment 200; contradiction 200; neutral 200 |
| Language | MSA 150; Egyptian 150; Arabic/English code-switch 180; transliteration 60; English diagnostic 60 |
| Difficulty | paraphrase entailment 180; entailment preservation 20; near-neighbor contradiction 110; direct contradiction 90; technical neutral 120; adjacent neutral 80 |
| Technical coverage | {validation['counts']['technical_examples']} / 600 |

## Leakage and integrity

- CP-005 SHA and `do_not_train=true`: verified.
- Protected CP-005 question-ID hits: `0`; additional DS-014 evaluation exclusion: enforced.
- Normalized evaluation premise/hypothesis/pair hits: `0/0/0`.
- Duplicate case IDs/pairs: `0/0`.
- Train/dev question overlap, semantic-family overlap, and paired-group overlap: `0/0/0`.
- Maximum token-Jaccard similarity against any CP-005 premise/hypothesis: `{validation['leakage']['maximum_observed_token_jaccard']:.6f}`; hard flags at `>=0.8`: `0`.
- Canonical source/provenance failures: `0`.
- Manual semantic-family review remains `PENDING`; automated similarity is not a substitute.

## Human review gate

- Every candidate requires two independent domain-qualified human reviewers.
- Near-neighbor contradictions and adjacent neutrals are explicitly ambiguity-flagged.
- Review must confirm the label, scope, language/dialect fidelity, source independence, and absence of a CP-005 semantic derivative.
- Disagreements require adjudication. No record may set `accepted_for_training=true` before this gate closes.

## Frozen hashes

- Corpus: `{corpus_sha}`
- Review ledger: `{review_sha}`
- Split manifest: `{split_sha}`
- Preflight validation: `{validation_sha}`
- Reference corpus: `{REFDOC_SHA256}`
- CP-005 exclusion source: `{CP005_SHA256}`

## Exact next step

Complete two independent human reviews for all 600 candidates, adjudicate disagreements, rerun/freeze the corpus and leakage validation, and only then request separate LoRA training authorization. Do not load a model or train while any ledger entry remains pending.
"""
    quality_path.write_text(quality, encoding="utf-8")

    print("PHASE2B_DATA_AUTHORING=PARTIAL_PASS_HUMAN_REVIEW_REQUIRED")
    print(f"CORPUS_RECORDS={len(records)}")
    print(f"CORPUS_SHA256={corpus_sha}")
    print(f"REVIEW_LEDGER_SHA256={review_sha}")
    print(f"SPLIT_MANIFEST_SHA256={split_sha}")
    print(f"VALIDATION_SHA256={validation_sha}")
    print(f"QUALITY_REPORT_SHA256={sha256_file(quality_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
