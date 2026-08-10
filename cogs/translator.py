import os
import discord
from discord.ext import commands
from google import genai

class Translator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # ── KONFIGURACJA MOSTEK MULTI-KANAŁOWYCH ──────────────────────────────
        # Struktura: ID_KANAŁU_ŹRÓDŁOWEGO : [ (ID_KANAŁU_DOCELOWEGO, "JĘZYK_DOCELOWY"), ... ]
        # Zamień przykładowe liczby poniżej na prawdziwe ID kanałów ze swojego serwera Discord!
        self.channel_bridges = {
            # Przykładowo: Z czatu polskiego -> na angielski
            111111111111111111: [
                (222222222222222222, "English")
            ],
            
            # Przykładowo: Z czatu angielskiego -> na polski oraz urdu
            222222222222222222: [
                (111111111111111111, "Polish"),
                (333333333333333333, "Urdu")
            ],

            # Przykładowo: Z czatu urdu/bengalskiego -> na angielski i polski
            333333333333333333: [
                (222222222222222222, "English"),
                (111111111111111111, "Polish")
            ]
        }

        # Pobieranie klucza z zmiennej środowiskowej lub z pliku gemini_key.txt
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key and os.path.exists("gemini_key.txt"):
            with open("gemini_key.txt", "r", encoding="utf-8") as f:
                api_key = f.read().strip()

        self.client = genai.Client(api_key=api_key) if api_key else None

    # ── 1. RĘCZNA KOMENDA TŁUMACZA (!tl / /tl) ─────────────────────────────────
    @commands.hybrid_command(
        name="tl", 
        description="Tłumaczy tekst na wybrany język (domyślnie angielski)."
    )
    async def translate(self, ctx: commands.Context, target_lang: str = "English", *, text: str = None):
        if not self.client:
            await ctx.send("❌ Brak klucza API Gemini. Dodaj klucz do pliku `gemini_key.txt` lub zmiennej środowiskowej.", ephemeral=True)
            return

        # Obsługa sytuacji, gdy ktoś napisze bezpośrednio: !tl Cześć co tam (bez podawania języka)
        if text is None and target_lang:
            known_langs = ["pl", "polish", "polski", "en", "english", "angielski", "es", "ur", "urdu", "bn", "bengali"]
            if len(target_lang.split()) > 1 or target_lang.lower() not in known_langs:
                text = target_lang
                target_lang = "English"

        # Obsługa odpowiedzi (Reply) na czyjąś wiadomość
        if not text and ctx.message and ctx.message.reference:
            ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            text = ref_msg.content

        if not text:
            await ctx.send("Wpisz tekst do przetłumaczenia lub odpowiedz tą komendą na czyjąś wiadomość!", ephemeral=True)
            return

        await ctx.defer()
        translated_text = await self._get_translation(text, target_lang)
        await ctx.send(f"**Tłumaczenie ({target_lang}):**\n{translated_text}")

    # ── 2. AUTOMATYCZNY MOSTEK MIĘDZY KANAŁAMI ────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignoruj wiadomości botów i puste wiadomości
        if message.author.bot or not message.content.strip():
            return

        # Jeśli kanał jest na liście mostków, przesyłamy automatyczne tłumaczenia
        if message.channel.id in self.channel_bridges:
            for target_channel_id, target_lang in self.channel_bridges[message.channel.id]:
                target_channel = self.bot.get_channel(target_channel_id)

                if target_channel:
                    translated_text = await self._get_translation(message.content, target_lang)
                    
                    relay_msg = (
                        f"💬 **[{message.author.display_name}]** (z #{message.channel.name}):\n"
                        f"{translated_text}"
                    )
                    await target_channel.send(relay_msg)

    # ── 3. POMOCNICZA FUNKCJA DO KOMUNIKACJI Z GEMINI ─────────────────────────
    async def _get_translation(self, text: str, target_lang: str) -> str:
        prompt = f"""
        Jesteś ekspertem wielojęzycznym i tłumaczem czatów w grach online.
        Przetłumacz poniższą wiadomość na język: {target_lang}.

        ZASADY TŁUMACZENIA:
        1. Bądź wyczulony na slang, skróty, zwroty potoczne oraz pisownię fonetyczną alfabetem łacińskim (np. Banglish, Roman Urdu, potoczny angielski/polski).
        2. Przekładaj SENS i EMOCJE wypowiedzi, zachowując naturalny, czatowy charakter.
        3. Odpowiedź zwróć w zwięzłej formie:
           - **[Wykryty język / styl]**
           - Przetłumaczony tekst

        Tekst do przetłumaczenia:
        "{text}"
        """
        try:
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"❌ Błąd tłumaczenia: {e}"

async def setup(bot):
    await bot.add_cog(Translator(bot))
