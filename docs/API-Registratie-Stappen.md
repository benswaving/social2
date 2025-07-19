# Social Media API Registratie - Stap-voor-Stap Guide

**Geschatte tijd:** 2-3 uur  
**Kosten:** Meeste gratis, Twitter $100/maand  

---

## 🔵 Facebook & Instagram API

### Stap 1: Facebook Developer Account
1. Ga naar [developers.facebook.com](https://developers.facebook.com)
2. Log in met je Facebook account
3. Klik "Get Started" rechtsboven
4. Kies "Developer" als account type
5. Vul je telefoonnummer in voor verificatie

### Stap 2: Facebook App Maken
1. Klik "Create App" in dashboard
2. Kies "Business" use case
3. Vul in:
   - **App Display Name**: "AI Social Media Creator"
   - **App Contact Email**: jouw email adres
   - **Business Manager Account**: Maak nieuwe aan
4. Klik "Create App"

### Stap 3: Instagram Basic Display Setup
1. In je app dashboard, scroll naar "Add a Product"
2. Zoek "Instagram Basic Display" → klik "Set Up"
3. Klik "Create New App"
4. Ga naar "Basic Display" → "Basic Display"
5. Scroll naar "Instagram App ID" en "Instagram App Secret"
6. **NOTEER DEZE WAARDES** ✍️

### Stap 4: Facebook Login Setup
1. Terug naar app dashboard
2. "Add a Product" → "Facebook Login" → "Set Up"
3. Kies "Web" platform
4. Site URL: `http://localhost:3000` (voor testing)
5. Ga naar "Settings" → "Basic"
6. **NOTEER App ID en App Secret** ✍️

### Stap 5: Permissions Aanvragen
1. Ga naar "App Review" → "Permissions and Features"
2. Vraag aan:
   - `instagram_basic`
   - `pages_show_list`
   - `pages_read_engagement`
   - `publish_to_groups` (voor posting)
3. Vul business verification formulier in
4. **Wachttijd: 3-7 dagen**

---

## 🔵 LinkedIn API

### Stap 1: LinkedIn Developer Account
1. Ga naar [developer.linkedin.com](https://developer.linkedin.com)
2. Log in met je LinkedIn account
3. Klik "Create App" rechtsboven

### Stap 2: App Registratie
1. Vul formulier in:
   - **App Name**: "AI Social Media Creator"
   - **LinkedIn Page**: Je moet een LinkedIn bedrijfspagina hebben
     - Ga naar [linkedin.com/company/setup/new](https://linkedin.com/company/setup/new)
     - Maak bedrijfspagina aan voor je app
   - **Privacy Policy URL**: `https://jouw-domain.com/privacy`
   - **App Logo**: Upload een 300x300px logo
2. Accepteer API Terms of Use
3. Klik "Create App"

### Stap 3: Products Aanvragen
1. In je app dashboard, ga naar "Products"
2. Klik "Request Access" voor:
   - **Sign In with LinkedIn** (meestal direct goedgekeurd)
   - **Share on LinkedIn** (review proces)
   - **Marketing Developer Platform** (voor advanced features)

### Stap 4: API Keys Verkrijgen
1. Ga naar "Auth" tab
2. **NOTEER deze waardes:** ✍️
   - **Client ID**
   - **Client Secret**
3. Voeg Redirect URLs toe:
   - `http://localhost:3000/auth/linkedin/callback`
   - `https://jouw-domain.com/auth/linkedin/callback`

### Stap 5: Verification Process
1. LinkedIn stuurt email voor verification
2. Vul business details in:
   - Bedrijfsnaam
   - Website URL
   - Beschrijving van je app
   - Hoe je LinkedIn data gebruikt
3. **Wachttijd: 1-5 dagen**

---

## 🔵 Twitter/X API

### Stap 1: Twitter Developer Account
1. Ga naar [developer.twitter.com](https://developer.twitter.com)
2. Log in met je Twitter account
3. Klik "Sign up for free account"

### Stap 2: Use Case Formulier
1. Vul gedetailleerd formulier in:
   - **Primary reason**: "Building a social media management tool"
   - **Country**: Nederland
   - **Use case details**: 
     ```
     Ik bouw een AI-powered social media management tool die gebruikers helpt 
     content te creëren en te posten op verschillende platforms. De tool gebruikt 
     Twitter API om:
     - Posts te publiceren namens gebruikers
     - Account informatie op te halen
     - Engagement metrics te analyseren
     
     De tool is bedoeld voor kleine bedrijven en marketeers om hun social media 
     presence te verbeteren met AI-gegenereerde content.
     ```
   - **Will you make Twitter content available to government**: **NO**
   - **Will you display Twitter content off Twitter**: **NO**

### Stap 3: Account Verification
1. Bevestig je email adres
2. Voeg telefoonnummer toe voor 2FA
3. Wacht op approval email (meestal binnen 24 uur)

### Stap 4: Project & App Maken
1. In developer dashboard, klik "Create Project"
2. Project details:
   - **Name**: "AI Social Creator"
   - **Use case**: "Making a bot"
   - **Description**: "AI social media management tool"
3. Maak app binnen project:
   - **App name**: "AI Social Creator App"
   - **Environment**: "Production"

### Stap 5: API Keys Verkrijgen
1. Ga naar je app → "Keys and Tokens"
2. **NOTEER deze waardes:** ✍️
   - **API Key** (Consumer Key)
   - **API Secret** (Consumer Secret)
   - **Bearer Token**
3. Generate Access Token:
   - Klik "Generate" onder "Access Token and Secret"
   - **NOTEER:** Access Token en Access Token Secret ✍️

### Stap 6: Upgrade naar Basic Plan
1. Voor posting functionaliteit: upgrade naar Basic ($100/maand)
2. Ga naar "Billing" → "Subscribe to Basic"
3. Vul betalingsgegevens in

---

## 🔵 TikTok API

### Stap 1: TikTok Developer Account
1. Ga naar [developers.tiktok.com](https://developers.tiktok.com)
2. Klik "Register" rechtsboven
3. Log in met je TikTok account
4. Kies "Developer" account type

### Stap 2: Business Verification
1. Vul business informatie in:
   - **Company Name**: Je bedrijfsnaam
   - **Business Email**: Zakelijk email adres
   - **Website**: Je website URL
   - **Industry**: "Technology/Software"
   - **Company Size**: Kies passende optie

### Stap 3: App Registratie
1. Klik "Create an App"
2. App details:
   - **App Name**: "AI Social Media Creator"
   - **Category**: "Productivity"
   - **Platform**: "Web"
   - **Description**: 
     ```
     AI-powered social media management tool that helps users create and 
     schedule content across multiple platforms including TikTok.
     ```

### Stap 4: API Products Aanvragen
1. In app dashboard, ga naar "Add Products"
2. Vraag toegang aan voor:
   - **Login Kit** (voor authenticatie)
   - **Content Posting API** (voor video uploads)
   - **Research API** (voor analytics)

### Stap 5: API Keys
1. Ga naar "Manage Apps" → je app
2. **NOTEER deze waardes:** ✍️
   - **Client Key**
   - **Client Secret**

### Stap 6: Review Process
1. TikTok review kan 1-3 weken duren
2. Ze kunnen aanvullende documentatie vragen
3. Wees geduldig - TikTok is streng met API access

---

## 🔵 Aanvullende AI APIs (Optioneel)

### Stability AI (voor betere afbeeldingen)
1. Ga naar [platform.stability.ai](https://platform.stability.ai)
2. Maak account aan
3. Ga naar "API Keys"
4. Generate nieuwe key
5. **NOTEER API Key** ✍️
6. **Kosten**: $0.04 per afbeelding

### Runway ML (voor video generatie)
1. Ga naar [runwayml.com](https://runwayml.com)
2. Join waitlist voor API access
3. **Status**: Nog in beta, beperkte toegang

---

## 📝 API Keys Overzicht Template

**Maak een veilig document met al je keys:**

```
=== AI SOCIAL MEDIA CREATOR API KEYS ===

OPENAI:
- API Key: sk-...
- Organization: org-...

FACEBOOK/INSTAGRAM:
- App ID: 123456789
- App Secret: abc123...
- Instagram App ID: 987654321
- Instagram App Secret: def456...

LINKEDIN:
- Client ID: 78abc123def
- Client Secret: ghi789...

TWITTER:
- API Key: xyz789...
- API Secret: uvw456...
- Access Token: 123-abc...
- Access Token Secret: def789...
- Bearer Token: AAAA...

TIKTOK:
- Client Key: aw123...
- Client Secret: bx456...

STABILITY AI:
- API Key: sk-...

=== REDIRECT URLS ===
- Facebook: http://localhost:3000/auth/facebook/callback
- Instagram: http://localhost:3000/auth/instagram/callback
- LinkedIn: http://localhost:3000/auth/linkedin/callback
- Twitter: http://localhost:3000/auth/twitter/callback
- TikTok: http://localhost:3000/auth/tiktok/callback
```

---

## ⚠️ Belangrijke Opmerkingen

### Security:
- **NOOIT** API keys in code committen
- Gebruik altijd environment variables
- Bewaar keys in password manager
- Regenereer keys als ze gecompromitteerd zijn

### Rate Limits:
- **Twitter**: 300 posts/15min (Basic plan)
- **LinkedIn**: 100 posts/dag per gebruiker
- **Facebook**: 200 posts/uur
- **Instagram**: 25 posts/dag
- **TikTok**: 100 posts/dag

### Approval Tips:
1. **Wees specifiek** in je use case beschrijvingen
2. **Vermeld AI/automation** expliciet
3. **Geef voorbeelden** van hoe je de API gebruikt
4. **Heb een werkende website** klaar
5. **Wees geduldig** - reviews kunnen weken duren

### Kosten Overzicht:
- **OpenAI**: ~$0.002 per 1K tokens
- **Facebook/Instagram**: Gratis
- **LinkedIn**: Gratis (basis features)
- **Twitter**: $100/maand (Basic plan)
- **TikTok**: Gratis (met rate limits)
- **Stability AI**: $0.04 per afbeelding

---

## 🆘 Troubleshooting

### "App Under Review":
- Wacht geduldig op approval
- Check email voor updates
- Respond snel op vragen van reviewers

### "Invalid Redirect URI":
- Controleer exact match in app settings
- Include http:// of https://
- Test met localhost eerst

### "Insufficient Permissions":
- Check welke permissions je app heeft
- Vraag extra permissions aan indien nodig
- Sommige permissions vereisen business verification

### Rate Limit Errors:
- Implementeer exponential backoff
- Cache responses waar mogelijk
- Spread requests over tijd

---

**🎯 Success Tip:** Begin met Facebook/Instagram en LinkedIn - deze zijn meestal het snelst goedgekeurd. Twitter en TikTok kun je later toevoegen als je app al draait.

