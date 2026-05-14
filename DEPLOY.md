# TradePrep Pro — Deployment Guide

## Quick Deploy (from phone)

### Option 1: Vercel CLI (laptop, 2 minutes)
```bash
git init && git add . && git commit -m "initial"
npx vercel --prod
```

### Option 2: GitHub + Vercel (phone-friendly)
1. Push this folder to a new GitHub repo (github.com/new → "tradeprepro")
2. Go to vercel.com/new
3. Import the GitHub repo
4. Add environment variable: ANTHROPIC_API_KEY = your key
5. Click Deploy

### Environment Variables (set in Vercel dashboard)
- ANTHROPIC_API_KEY — your Anthropic API key (for AI Tutor)
- STRIPE_SECRET_KEY — your Stripe secret key (for subscriptions)
- NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY — Stripe publishable key

### After Deploy
- Add custom domain in Vercel: Settings → Domains
- Suggested: tradeprepro.ca or redsealprep.ca
