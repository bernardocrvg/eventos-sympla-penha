#!/usr/bin/env python3
"""
Processador de Eventos Sympla 100% Independente - VERSÃO CORRIGIDA
Roda no GitHub Actions sem depender de nenhum servidor externo
CORREÇÃO: Filtra apenas "Curso Online de Pais e Padrinhos", exclui "Curso de Noivos"
"""

import os
import json
import requests
import re
from datetime import datetime, timedelta
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
    
    def fetch_all_events(self) -> List[Dict[str, Any]]:
        """Busca todos os eventos da API Sympla"""
        print("🔍 Buscando eventos do Sympla...")
        
        all_events = []
        page = 1
        max_pages = 20
        
        while page <= max_pages:
            endpoint = f"{self.api_base_url}/events?page={page}&page_size=100&published=true"
            
            try:
                print(f"📡 Página {page}: {endpoint}")
                response = requests.get(endpoint, headers=self.headers, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if isinstance(data, dict) and 'data' in data:
                        page_items = data['data']
                        print(f"📊 Página {page}: {len(page_items)} items")
                        
                        if len(page_items) == 0:
                            print(f"🏁 Página {page} vazia - fim da paginação")
                            break
                        
                        page_events = self.process_sympla_events(page_items)
                        if page_events:
                            all_events.extend(page_events)
                            print(f"✅ Página {page}: {len(page_events)} eventos processados")
                        
                        page += 1
                    else:
                        print(f"⚠️ Estrutura inesperada na página {page}")
                        break
                        
                elif response.status_code == 401:
                    raise ValueError("❌ API Key inválida")
                elif response.status_code == 403:
                    raise ValueError("❌ Sem permissão para acessar API")
                else:
                    print(f"⚠️ Status {response.status_code} na página {page}")
                    break
                    
            except Exception as e:
                print(f"❌ Erro na página {page}: {e}")
                break
        
        print(f"✅ Total de eventos únicos: {len(all_events)}")
        return all_events
    
    def process_sympla_events(self, events_data) -> List[Dict[str, Any]]:
        """Processa dados de eventos da API Sympla - COM FILTRO CORRIGIDO"""
        processed_events = []
        
        for event_info in events_data:
            try:
                if not isinstance(event_info, dict):
                    continue
                
                # Extrai informações básicas
                title = (event_info.get('name') or 
                        event_info.get('title') or 
                        event_info.get('event_name') or '')
                
                event_url = (event_info.get('url') or 
                            event_info.get('public_url') or
                            event_info.get('link') or '')
                
                event_id = event_info.get('id', '')
                
                if event_id and not event_url:
                    event_url = f"https://www.sympla.com.br/evento/{event_id}"
                
                if not title:
                    continue
                
                # ===== FILTRO PARA 3 TIPOS: Pais/Padrinhos e Noivos =====
                title_lower = title.lower()
                
                # Detecta cursos de noivos
                noivos_patterns = [
                    'curso de noivos',
                    'curso para noivos',
                    'curso online de noivos',
                    'noivos'
                ]
                
                # Detecta cursos de pais e padrinhos
                pais_patterns = [
                    'curso online de pais e padrinhos',
                    'curso de pais e padrinhos',
                    'pais e padrinhos'
                ]
                
                # Classifica o tipo de curso
                is_noivos = any(pattern in title_lower for pattern in noivos_patterns)
                is_pais = any(pattern in title_lower for pattern in pais_patterns)
                
                if not is_noivos and not is_pais:
                    print(f"❌ Rejeitado (não é curso reconhecido): {title[:50]}...")
                    continue
                
                if is_noivos:
                    print(f"💒 Aceito (curso de noivos): {title[:50]}...")
                    course_type = "noivos"
                else:
                    print(f"👶 Aceito (curso de pais): {title[:50]}...")
                    course_type = "pais"
                    
                # ===== FIM DO FILTRO PARA 3 TIPOS =====
                
                # Extrai data do evento
                event_date = None
                date_fields = ['start_date', 'date', 'event_date', 'start_time', 'begin_date']
                
                for field in date_fields:
                    if field in event_info and event_info[field]:
                        try:
                            date_value = event_info[field]
                            date_formats = [
                                '%Y-%m-%d',
                                '%Y-%m-%dT%H:%M:%S',
                                '%Y-%m-%d %H:%M:%S',
                                '%d/%m/%Y',
                                '%d-%m-%Y'
                            ]
                            
                            for fmt in date_formats:
                                try:
                                    event_date = datetime.strptime(str(date_value)[:19], fmt)
                                    break
                                except ValueError:
                                    continue
                            
                            if event_date:
                                break
                        except Exception:
                            continue
                
                # Se não conseguiu da API, tenta extrair do título
                if not event_date:
                    date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', title)
                    if date_match:
                        day, month, year = date_match.groups()
                        try:
                            event_date = datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y")
                        except ValueError:
                            continue
                
                if not event_date:
                    print(f"⚠️ Sem data válida: {title[:50]}...")
                    continue
                
                # Verifica se é evento futuro
                if event_date.date() < datetime.now().date():
                    print(f"⏰ Data passou: {title[:50]}...")
                    continue
                
                # Determina dia da semana
                weekday = event_date.strftime('%a')
                day_mapping = {
                    'Sun': 'Dom', 'Mon': 'Seg', 'Tue': 'Ter', 'Wed': 'Qua',
                    'Thu': 'Qui', 'Fri': 'Sex', 'Sat': 'Sáb'
                }
                day_of_week = day_mapping.get(weekday, 'Dom')
                
                # Determina tipo do evento e horário
                if course_type == "noivos":
                    event_type = "noivos"
                    # Cursos de noivos geralmente são sábados às 14:00
                    time_str = "14:00"
                elif ("na basílica" in title_lower or "na basilica" in title_lower):
                    event_type = "penha"
                    time_str = "15:00" if day_of_week == 'Dom' else "11:00"
                elif ("fora da basílica" in title_lower or "fora da basilica" in title_lower):
                    event_type = "outras"
                    time_str = "14:00" if day_of_week == 'Dom' else "11:00"
                else:
                    # Para cursos de pais sem especificação, assume "outras"
                    event_type = "outras"
                    time_str = "14:00" if day_of_week == 'Dom' else "11:00"
                
                # Cria dados do evento
                event_data = {
                    'id': event_id or f"evento-{event_date.strftime('%Y%m%d')}",
                    'title': title.strip(),
                    'date': event_date.strftime("%d/%m/%Y"),
                    'time': time_str,
                    'day_of_week': day_of_week,
                    'sympla_url': event_url,
                    'event_type': event_type,
                    'full_date_time': event_date.isoformat(),
                    'created_at': datetime.utcnow().isoformat()
                }
                
                processed_events.append(event_data)
                print(f"🎯 Processado: {event_date.strftime('%d/%m/%Y')} - {event_type} - {day_of_week}")
                
            except Exception as e:
                print(f"⚠️ Erro processando evento: {e}")
                continue
        
        return processed_events
    
    def generate_html(self, penha_events: List[Dict], outras_events: List[Dict], noivos_events: List[Dict]) -> tuple:
        """Gera HTML estático e dinâmico com design aplicado"""
        
        # CSS comum com design final
        common_css = '''
        @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;700;900&display=swap');
        
        .event-container { 
            font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            width: 100%;
            max-width: none;
            margin: 0;
            padding: 0;
            background: transparent;
            min-height: auto;
            box-sizing: border-box;
            text-align: center;
        }
        
        .month-section { 
            margin-bottom: 25px; 
            background: transparent;
            padding: 15px 10px;
        }
        
        .month-section h2 { 
            font-family: 'Montserrat', sans-serif;
            font-weight: 900;
            color: #003448;
            margin-bottom: 15px;
            font-size: 18px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            text-align: center;
            padding: 0;
        }
        
        .event-button {
            display: inline-block;
            background: linear-gradient(145deg, #ffffff 0%, #f8f9fa 100%);
            color: #003448;
            font-family: 'Montserrat', sans-serif;
            font-weight: 700;
            font-size: 14px;
            padding: 12px 20px;
            margin: 6px 8px 6px 0;
            text-decoration: none;
            border-radius: 25px;
            border: none;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1), 0 2px 4px rgba(0, 0, 0, 0.06);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            text-align: center;
            line-height: 1.2;
        }
        
        .event-button:hover {
            background: linear-gradient(145deg, #a2d2ff 0%, #7cc7ff 100%);
            color: #003448;
            text-decoration: none;
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15), 0 3px 6px rgba(0, 0, 0, 0.1);
        }
        
        .update-info {
            margin-top: 20px; 
            padding: 10px 15px; 
            background: rgba(248, 249, 250, 0.8);
            border-radius: 15px; 
            text-align: center; 
            color: #6b7280; 
            font-size: 11px;
            font-family: 'Montserrat', sans-serif;
            font-weight: 400;
            border: 1px solid rgba(226, 232, 240, 0.5);
        }
        
        @media (max-width: 768px) {
            .event-button {
                display: block;
                width: calc(100% - 16px);
                margin: 6px 8px;
                text-align: center;
            }
            .month-section h2 {
                font-size: 16px;
            }
        }
        
        @media (max-width: 480px) {
            .event-button {
                width: calc(100% - 8px);
                margin: 4px 4px;
                padding: 10px 15px;
                font-size: 13px;
            }
            .month-section h2 {
                font-size: 15px;
            }
        }
        '''
        
        def organize_by_month(events):
            """Organiza eventos por mês/ano"""
            by_month = {}
            for event in events:
                event_date = datetime.fromisoformat(event['full_date_time'])
                month_names = {
                    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
                    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
                    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
                }
                month_year = f"{month_names[event_date.month]}/{event_date.year}"
                
                if month_year not in by_month:
                    by_month[month_year] = []
                by_month[month_year].append(event)
            
            return by_month
        
        def generate_buttons_html(events_by_month):
            """Gera HTML dos botões organizados por mês"""
            if not events_by_month:
                return '<div style="text-align: center; padding: 40px; color: #666;"><p>Nenhum evento disponível no momento.</p></div>'
            
            html = ''
            # Ordena meses cronologicamente
            sorted_months = sorted(events_by_month.keys(), key=lambda x: (
                int(x.split('/')[1]),  # ano
                list(events_by_month.keys()).index(x) if x in events_by_month else 999  # mês
            ))
            
            for month_year in sorted_months:
                html += f'<div class="month-section">'
                html += f'<h2>{month_year.upper()}</h2>'
                
                # Ordena eventos por data dentro do mês
                sorted_events = sorted(events_by_month[month_year], 
                                     key=lambda x: datetime.fromisoformat(x['full_date_time']))
                
                for event in sorted_events:
                    # Mapeia dia da semana
                    day_names = {
                        "Dom": "DOMINGO", "Seg": "SEGUNDA-FEIRA", "Ter": "TERÇA-FEIRA",
                        "Qua": "QUARTA-FEIRA", "Qui": "QUINTA-FEIRA", "Sex": "SEXTA-FEIRA",
                        "Sáb": "SÁBADO"
                    }
                    day_name = day_names.get(event['day_of_week'], event['day_of_week'].upper())
                    button_text = f'{event["date"]} ({day_name})'
                    html += f'<a href="{event["sympla_url"]}" target="_blank" class="event-button">{button_text}</a>'
                
                html += '</div>'
            
            return html
        
        # Organiza eventos por mês
        penha_by_month = organize_by_month(penha_events)
        outras_by_month = organize_by_month(outras_events)
        noivos_by_month = organize_by_month(noivos_events)
        
        # Gera HTML para Igreja da Penha
        penha_buttons = generate_buttons_html(penha_by_month)
        html_penha = f'''
        <div class="event-container">
            <style>{common_css}</style>
            {penha_buttons}
            <div class="update-info">
                Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')} UTC
            </div>
        </div>
        '''
        
        # Gera HTML para Outras Igrejas  
        outras_buttons = generate_buttons_html(outras_by_month)
        html_outras = f'''
        <div class="event-container">
            <style>{common_css}</style>
            {outras_buttons}
            <div class="update-info">
                Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')} UTC
            </div>
        </div>
        '''
        
        # Gera HTML para Cursos de Noivos
        noivos_buttons = generate_buttons_html(noivos_by_month)
        html_noivos = f'''
        <div class="event-container">
            <style>{common_css}</style>
            {noivos_buttons}
            <div class="update-info">
                Última atualização: {datetime.now().strftime('%d/%m/%Y às %H:%M')} UTC
            </div>
        </div>
        '''
        
        return html_penha, html_outras, html_noivos
    
    def process_all_events(self):
        """Processo completo: busca eventos e gera HTML"""
        print("🚀 Iniciando processamento completo dos eventos...")
        
        # Busca eventos da API
        all_events = self.fetch_all_events()
        
        if not all_events:
            print("⚠️ Nenhum evento encontrado")
            return None
        
        # Separa por categoria
        penha_events = [e for e in all_events if e['event_type'] == 'penha']
        outras_events = [e for e in all_events if e['event_type'] == 'outras']
        noivos_events = [e for e in all_events if e['event_type'] == 'noivos']
        
        print(f"📊 Igreja da Penha: {len(penha_events)} eventos")
        print(f"📊 Outras Igrejas: {len(outras_events)} eventos")
        print(f"💒 Cursos de Noivos: {len(noivos_events)} eventos")
        
        # Gera HTML
        html_penha, html_outras, html_noivos = self.generate_html(penha_events, outras_events, noivos_events)
        
        # Dados finais
        result = {
            'penha_events': penha_events,
            'outras_events': outras_events,
            'noivos_events': noivos_events,
            'html_penha': html_penha,
            'html_outras': html_outras,
            'html_noivos': html_noivos,
            'penha_events_count': len(penha_events),
            'outras_events_count': len(outras_events),
            'noivos_events_count': len(noivos_events),
            'total_events': len(all_events),
            'last_update': datetime.utcnow().isoformat(),
            'generated_at': datetime.utcnow().strftime('%d/%m/%Y às %H:%M UTC')
        }
        
        print(f"✅ Processamento concluído: {result['total_events']} eventos")
        return result

def main():
    """Função principal para execução no GitHub Actions"""
    try:
        processor = SymplaProcessor()
        result = processor.process_all_events()
        
        if not result:
            print("❌ Falha no processamento")
            exit(1)
        
        # Salva dados em JSON para uso posterior
        with open('events-data.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print("✅ Dados salvos em events-data.json")
        return result
        
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        exit(1)

if __name__ == "__main__":
    main()
