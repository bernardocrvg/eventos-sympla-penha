#!/usr/bin/env python3
"""
Processador de Eventos Sympla 100% Independente
Gera dados e fragments de HTML (sem <style>) para o GitHub Pages
"""

import os
import json
import requests
import re
from datetime import datetime, timezone
from typing import List, Dict, Any


class SymplaProcessor:
    def __init__(self):
        self.api_key = os.environ.get('SYMPLA_API_KEY')
        self.api_base_url = "https://api.sympla.com.br/public/v1.5.1"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'S_TOKEN': self.api_key,
            'Content-Type': 'application/json'
        }
        if not self.api_key:
            raise ValueError("❌ SYMPLA_API_KEY não encontrada nas variáveis de ambiente")

    # -----------------------------
    # BUSCA E PRÉ-PROCESSAMENTO
    # -----------------------------
    def fetch_all_events(self) -> List[Dict[str, Any]]:
        """Busca eventos publicados na API Sympla com paginação."""
        print("🔍 Buscando eventos do Sympla...")
        all_events = []
        page, max_pages = 1, 20

        while page <= max_pages:
            endpoint = f"{self.api_base_url}/events?page={page}&page_size=100&published=true"
            try:
                print(f"📡 Página {page}: {endpoint}")
                resp = requests.get(endpoint, headers=self.headers, timeout=30)

                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and 'data' in data:
                        items = data['data']
                        print(f"📊 Página {page}: {len(items)} items")
                        if not items:
                            print(f"🏁 Página {page} vazia - fim da paginação")
                            break

                        page_events = self.process_sympla_events(items)
                        if page_events:
                            all_events.extend(page_events)
                            print(f"✅ Página {page}: {len(page_events)} eventos processados")
                        page += 1
                    else:
                        print(f"⚠️ Estrutura inesperada na página {page}")
                        break
                elif resp.status_code == 401:
                    raise ValueError("❌ API Key inválida")
                elif resp.status_code == 403:
                    raise ValueError("❌ Sem permissão para acessar API")
                else:
                    print(f"⚠️ Status {resp.status_code} na página {page}")
                    break
            except Exception as e:
                print(f"❌ Erro na página {page}: {e}")
                break

        # Deduplicação simples por ID
        seen, unique = set(), []
        for ev in all_events:
            k = ev.get('id')
            if k not in seen:
                seen.add(k)
                unique.append(ev)

        print(f"✅ Total de eventos únicos: {len(unique)}")
        return unique

    def process_sympla_events(self, events_data) -> List[Dict[str, Any]]:
        """
        Converte objetos crus da Sympla em um formato padronizado
        e filtra apenas os eventos relevantes (curso de pais/padrinhos/batizado),
        apenas futuros.
        """
        processed = []
        for raw in events_data:
            try:
                if not isinstance(raw, dict):
                    continue

                title = (raw.get('name') or raw.get('title') or raw.get('event_name') or '').strip()
                if not title:
                    continue

                # Filtro de relevância (ajuste palavras-chave se necessário)
                t_lower = title.lower()
                keywords = ['curso', 'pais', 'padrinhos', 'batizado']
                if not any(k in t_lower for k in keywords):
                    continue

                event_url = (raw.get('url') or raw.get('public_url') or raw.get('link') or '')
                event_id = raw.get('id', '')
                if event_id and not event_url:
                    event_url = f"https://www.sympla.com.br/evento/{event_id}"

                # Tenta extrair data
                event_date = None
                for field in ['start_date', 'date', 'event_date', 'start_time', 'begin_date']:
                    val = raw.get(field)
                    if not val:
                        continue
                    for fmt in ('%Y-%m-%d',
                                '%Y-%m-%dT%H:%M:%S',
                                '%Y-%m-%d %H:%M:%S',
                                '%d/%m/%Y',
                                '%d-%m-%Y'):
                        try:
                            event_date = datetime.strptime(str(val)[:19], fmt)
                            break
                        except ValueError:
                            pass
                    if event_date:
                        break

                if not event_date:
                    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', title)
                    if m:
                        d, mth, y = m.groups()
                        try:
                            event_date = datetime.strptime(f"{d}/{mth}/{y}", "%d/%m/%Y")
                        except ValueError:
                            pass
                if not event_date:
                    continue

                # Mantém apenas futuros
                if event_date.date() < datetime.now().date():
                    continue

                weekday = event_date.strftime('%a')
                day_mapping = {
                    'Sun': 'Dom', 'Mon': 'Seg', 'Tue': 'Ter', 'Wed': 'Qua',
                    'Thu': 'Qui', 'Fri': 'Sex', 'Sat': 'Sáb'
                }
                day_of_week = day_mapping.get(weekday, 'Dom')

                # Heurística de tipo e horário
                if ("na basílica" in t_lower or "na basilica" in t_lower):
                    event_type = "penha"
                    time_str = "15:00" if day_of_week == 'Dom' else "11:00"
                elif ("fora da basílica" in t_lower or "fora da basilica" in t_lower):
                    event_type = "outras"
                    time_str = "14:00" if day_of_week == 'Dom' else "11:00"
                else:
                    event_type = "outras"
                    time_str = "14:00" if day_of_week == 'Dom' else "11:00"

                processed.append({
                    'id': event_id or f"evento-{event_date.strftime('%Y%m%d')}",
                    'title': title,
                    'date': event_date.strftime("%d/%m/%Y"),
                    'time': time_str,
                    'day_of_week': day_of_week,
                    'sympla_url': event_url,
                    'event_type': event_type,
                    'full_date_time': event_date.isoformat(),
                    'created_at': datetime.now(timezone.utc).isoformat()
                })
            except Exception as e:
                print(f"⚠️ Erro processando evento: {e}")
                continue

        return processed

    # -----------------------------
    # GERAÇÃO DE HTML (FRAGMENTS SEM <style>)
    # -----------------------------
    def _month_key(self, month_year: str):
        nome, ano = month_year.split("/")
        mapa = {
            "Janeiro": 1, "Fevereiro": 2, "Março": 3, "Marco": 3,
            "Abril": 4, "Maio": 5, "Junho": 6, "Julho": 7,
            "Agosto": 8, "Setembro": 9, "Outubro": 10,
            "Novembro": 11, "Dezembro": 12
        }
        return (int(ano), mapa.get(nome, 1))

    def _organize_by_month(self, events: List[Dict]) -> Dict[str, List[Dict]]:
        by_month: Dict[str, List[Dict]] = {}
        for ev in events:
            dt = datetime.fromisoformat(ev['full_date_time'])
            nome_mes = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"][dt.month-1]
            key = f"{nome_mes}/{dt.year}"
            by_month.setdefault(key, []).append(ev)
        return by_month

    def _render_buttons(self, events_by_month: Dict[str, List[Dict]]) -> str:
        if not events_by_month:
            return '<div class="empty">Nenhum evento disponível no momento.</div>'
        html = []
        for month_year in sorted(events_by_month.keys(), key=self._month_key):
            html.append(f'<section class="month"><h3>{month_year.upper()}</h3>')
            for ev in sorted(events_by_month[month_year], key=lambda x: datetime.fromisoformat(x['full_date_time'])):
                day_names = {
                    "Dom": "DOMINGO", "Seg": "SEGUNDA-FEIRA", "Ter": "TERÇA-FEIRA",
                    "Qua": "QUARTA-FEIRA", "Qui": "QUINTA-FEIRA", "Sex": "SEXTA-FEIRA", "Sáb": "SÁBADO"
                }
                dn = day_names.get(ev['day_of_week'], ev['day_of_week'].upper())
                label = f'{ev["date"]} ({dn})'
                html.append(f'<a class="event-btn" href="{ev["sympla_url"]}" target="_blank" rel="noopener">{label}</a>')
            html.append('</section>')
        return "\n".join(html)

    def generate_fragments(self, penha_events: List[Dict], outras_events: List[Dict]) -> Dict[str, str]:
        """Retorna fragments HTML SEM <style> e contagens."""
        penha_by = self._organize_by_month(penha_events)
        outras_by = self._organize_by_month(outras_events)
        html_penha = self._render_buttons(penha_by)
        html_outras = self._render_buttons(outras_by)
        return {
            "html_penha": html_penha,
            "html_outras": html_outras,
            "penha_events_count": len(penha_events),
            "outras_events_count": len(outras_events),
            "total_events": len(penha_events) + len(outras_events),
        }

    # -----------------------------
    # PIPELINE COMPLETO
    # -----------------------------
    def process_all_events(self):
        """Busca eventos, separa, gera fragments e retorna estrutura final."""
        print("🚀 Iniciando processamento completo dos eventos...")
        all_events = self.fetch_all_events()
        if not all_events:
            print("⚠️ Nenhum evento encontrado")
            return None

        penha_events = [e for e in all_events if e['event_type'] == 'penha']
        outras_events = [e for e in all_events if e['event_type'] == 'outras']

        print(f"📊 Igreja da Penha: {len(penha_events)} eventos")
        print(f"📊 Outras Igrejas: {len(outras_events)} eventos")

        frags = self.generate_fragments(penha_events, outras_events)

        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result = {
            'penha_events': penha_events,
            'outras_events': outras_events,
            'html_penha': frags['html_penha'],
            'html_outras': frags['html_outras'],
            'penha_events_count': frags['penha_events_count'],
            'outras_events_count': frags['outras_events_count'],
            'total_events': frags['total_events'],
            'last_update': now_iso,
            'generated_at': datetime.now(timezone.utc).strftime('%d/%m/%Y às %H:%M UTC')
        }
        print(f"✅ Processamento concluído: {result['total_events']} eventos")
        return result


def main():
    """Executa o pipeline e grava events-data.json (usado pelo workflow)."""
    try:
        processor = SymplaProcessor()
        result = processor.process_all_events()
        if not result:
            print("❌ Falha no processamento")
            raise SystemExit(1)

        with open('events-data.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print("✅ Dados salvos em events-data.json")
        return result
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
