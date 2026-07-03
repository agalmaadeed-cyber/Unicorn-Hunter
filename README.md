# 🦄 Unicorn Hunter

نظام داخلي متعدد الوكلاء لتوليد واختبار أفكار مشاريع رقمية وAI — بهدف إنتاج فرص MVP قابلة للبناء، مع بحث فعلي على الإنترنت وحلقة تحقق ميداني قبل أي قرار بناء.

## المعمارية

أربعة وكلاء متسلسلون:

1. **الاستكشاف** (`agents/discovery.py`) — يبحث فعلياً على الإنترنت (Web Search Tool) ويستخرج الفرص، مع مؤشر جودة مدخلات صادق.
2. **صياغة المشكلة** (`agents/problem_framing.py`) — يحوّل الفرصة لبطاقة مشكلة دقيقة.
3. **توليد الحلول** (`agents/solution_generator.py`) — ينتج 5+ حلول متنوعة.
4. **التقييم** (`agents/evaluation.py`) — تقييم أولي (تحليلي) + 3 أسئلة تحقق → إجابات المستخدم → تقييم ثانٍ (بعد التحقق الميداني).

التخزين: SQLite محلي (`storage/ideas.db`، يُنشأ تلقائياً). الخطة المستقبلية: الانتقال لـ Google Sheets API بعد التحقق من جودة النظام.

## التشغيل المحلي

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# ضع مفتاح ANTHROPIC_API_KEY الحقيقي داخل secrets.toml
streamlit run app.py
```

## ملاحظة مهمة عن التخزين

`storage/ideas.db` محلي فقط. عند النشر على Streamlit Cloud، الملف يُمسح مع كل إعادة نشر. هذا متوقع في هذه المرحلة (Lite) — الانتقال لتخزين سحابي دائم مخطط له لاحقاً.
