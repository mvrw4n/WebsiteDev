#!/usr/bin/env python
"""
Script pour exécuter directement le code de scraping sans passer par Celery
"""
import os
import sys
import django
import logging
import traceback
import socket
from django.utils import timezone

# Configurer le logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wizzydjango.settings.development')
django.setup()

def run_direct_debug(task_id):
    """Exécute directement le code qui serait normalement exécuté par run_scraping_task"""
    logger.info(f"=== DÉBOGAGE DIRECT DE LA TÂCHE {task_id} ===")
    
    try:
        # Importation des modèles nécessaires
        from scraping.models import ScrapingTask, ScrapingLog, ScrapingResult, ScrapedSite
        from core.models import ScrapingJob, ScrapingStructure, Lead
        import random
        import time
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse
        
        # Vérifier si la tâche existe
        task = ScrapingTask.objects.get(id=task_id)
        logger.info(f"Tâche trouvée: {task}")
        logger.info(f"  Job: {task.job.name}")
        logger.info(f"  Status: {task.status}")
        logger.info(f"  Current step: {task.current_step}")
        
        # ==== CODE RÉEL ÉQUIVALENT À run_scraping_task ====
        
        # Mettre à jour le statut
        task.status = 'initializing'
        task.current_step = "Initialisation de la tâche pour débogage direct..."
        task.save()
        
        # Ajouter un log
        ScrapingLog.objects.create(
            task=task,
            log_type='info',
            message=f"DEBUGGER: Exécution directe de la tâche sur {socket.gethostname()}",
            details={
                "worker": socket.gethostname(),
                "mode": "DEBUG"
            }
        )
        
        # Récupérer le job et la structure
        job = task.job
        if not job:
            raise ValueError("No job associated with this task")
            
        structure = job.structure
        if not structure:
            task.status = 'failed'
            task.error_message = "Aucune structure associée à cette tâche"
            task.completion_time = timezone.now()
            task.save()
            return False
            
        # Vérifier le quota de l'utilisateur
        profile = job.user.profile
        logger.info(f"Vérification des quotas utilisateur: {profile.leads_used}/{profile.leads_quota}")
        if not profile.unlimited_leads and profile.leads_used >= profile.leads_quota:
            logger.error(f"Quota utilisateur dépassé: {profile.leads_used}/{profile.leads_quota}")
            task.status = 'failed'
            task.current_step = 'Quota de leads dépassé'
            task.error_message = 'Votre quota de leads est épuisé. Veuillez passer à un forfait supérieur pour continuer.'
            task.completion_time = timezone.now()
            task.save()
            return False
            
        # Mettre à jour le statut pour commencer le crawling
        task.status = 'crawling'
        task.current_step = "Exploration des sites web..."
        task.save()
        
        # Log du début du scraping
        ScrapingLog.objects.create(
            task=task,
            log_type='info',
            message=f"DEBUGGER: Début du scraping avec requête: {job.search_query}",
            details={"search_query": job.search_query}
        )
        
        # Définir les sites à scraper
        sites_to_scrape = []
        
        # Utiliser une URL de test pour le débogage
        test_url = "https://example.com/contact"
        domain = "example.com"
        site, created = ScrapedSite.objects.get_or_create(
            url=test_url,
            structure=structure,
            defaults={
                'domain': domain,
                'last_scraped': None
            }
        )
        sites_to_scrape.append(site)
        
        # Log du site de test
        ScrapingLog.objects.create(
            task=task,
            log_type='info',
            message=f"DEBUGGER: Utilisation du site de débogage: {test_url}",
            details={"domain": domain}
        )
        
        # Parcourir les sites (en l'occurrence, juste un site de test)
        for site_index, site in enumerate(sites_to_scrape):
            task.current_step = f"Exploration du site {site_index+1}/{len(sites_to_scrape)}: {site.domain}"
            task.save()
            
            ScrapingLog.objects.create(
                task=task,
                log_type='info',
                message=f"DEBUGGER: Scraping de {site.url}",
                details={"site_index": site_index+1, "total_sites": len(sites_to_scrape)}
            )
            
            # Simuler du contenu HTML
            html_content = f"""
            <html>
            <head><title>Site de test {site.domain}</title></head>
            <body>
                <h1>Bienvenue sur {site.domain}</h1>
                <div class="contact-info">
                    <h2>Nos contacts</h2>
                    <ul>
                        <li>
                            <div class="person">
                                <h3>Jean Dupont</h3>
                                <p class="role">Directeur Commercial</p>
                                <p class="email">jean.dupont@{site.domain}</p>
                                <p class="phone">+33 6 12 34 56 78</p>
                            </div>
                        </li>
                        <li>
                            <div class="person">
                                <h3>Marie Martin</h3>
                                <p class="role">Responsable Marketing</p>
                                <p class="email">marie.martin@{site.domain}</p>
                                <p class="phone">+33 6 98 76 54 32</p>
                            </div>
                        </li>
                    </ul>
                </div>
            </body>
            </html>
            """
            
            # Log de la réponse
            ScrapingLog.objects.create(
                task=task,
                log_type='info',
                message=f"DEBUGGER: Page récupérée ({len(html_content)} caractères)",
                details={"content_size": len(html_content)}
            )
            
            # Analyser avec BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extraire les contacts
            contact_elements = soup.select('.person')
            
            logger.info(f"DEBUGGER: {len(contact_elements)} contacts trouvés sur la page")
            
            # Pour chaque contact
            for contact_element in contact_elements:
                # Extraire les données
                name = contact_element.select_one('h3').text.strip() if contact_element.select_one('h3') else "Inconnu"
                role = contact_element.select_one('.role').text.strip() if contact_element.select_one('.role') else ""
                email = contact_element.select_one('.email').text.strip() if contact_element.select_one('.email') else ""
                phone = contact_element.select_one('.phone').text.strip() if contact_element.select_one('.phone') else ""
                
                # Créer un dictionnaire pour le lead
                lead_data = {
                    "nom": name,
                    "fonction": role,
                    "email": email,
                    "telephone": phone,
                    "source": site.url,
                    "domaine": site.domain
                }
                
                # Log du lead trouvé
                ScrapingLog.objects.create(
                    task=task,
                    log_type='success',
                    message=f"DEBUGGER: Lead trouvé: {lead_data['nom']} ({lead_data['fonction']})",
                    details={"lead": lead_data}
                )
                
                # Incrémenter les compteurs
                task.pages_explored += 1
                task.leads_found += 1
                task.unique_leads += 1
                task.save()
                
                # Créer le résultat
                scraping_result = ScrapingResult.objects.create(
                    task=task,
                    lead_data=lead_data,
                    source_url=site.url,
                    is_duplicate=False
                )
                
                # Créer un lead depuis le résultat
                try:
                    lead = Lead.objects.create(
                        scraping_result=scraping_result,
                        user=job.user,
                        name=name,
                        email=email,
                        phone=phone,
                        company=site.domain,
                        position=role,
                        status='not_contacted',
                        source=f"Scraped from {structure.name}",
                        source_url=site.url,
                        data=lead_data
                    )
                    
                    # Mettre à jour le profil utilisateur
                    if not profile.unlimited_leads:
                        profile.leads_used += 1
                        profile.save()
                    
                    logger.info(f"DEBUGGER: Lead {lead.id} créé en base de données")
                except Exception as e:
                    logger.error(f"DEBUGGER ERROR: Erreur lors de la création du lead: {str(e)}")
            
            # Pause entre les sites
            time.sleep(1)
        
        # Terminer la tâche
        task.status = 'completed'
        task.current_step = "Tâche terminée avec succès"
        task.completion_time = timezone.now()
        task.save()
        
        # Mettre à jour le job
        job.leads_found = task.unique_leads
        job.status = 'completed'
        job.save()
        
        # Log final
        ScrapingLog.objects.create(
            task=task,
            log_type='success',
            message=f"DEBUGGER: Scraping terminé avec succès - {task.unique_leads} leads trouvés",
            details={
                "total_leads": task.leads_found,
                "unique_leads": task.unique_leads,
                "pages_explored": task.pages_explored,
                "mode": "DEBUG"
            }
        )
        
        logger.info(f"Tâche terminée avec succès: {task.unique_leads} leads trouvés")
        return True
        
    except Exception as e:
        logger.error(f"ERREUR: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Essayer de mettre à jour le statut de la tâche
        try:
            from scraping.models import ScrapingTask, ScrapingLog
            task = ScrapingTask.objects.get(id=task_id)
            task.status = 'failed'
            task.error_message = str(e)
            task.completion_time = timezone.now()
            task.save()
            
            ScrapingLog.objects.create(
                task=task,
                log_type='error',
                message=f"DEBUGGER ERROR: {str(e)}",
                details={"traceback": traceback.format_exc()}
            )
        except Exception as inner_e:
            logger.error(f"ERREUR supplémentaire: {str(inner_e)}")
            
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        task_id = int(sys.argv[1])
    else:
        # Demander l'ID de la tâche
        task_id = input("Entrez l'ID de la tâche à exécuter: ")
        task_id = int(task_id)
    
    success = run_direct_debug(task_id)
    
    if success:
        logger.info("✅ Débogage direct terminé avec succès")
        sys.exit(0)
    else:
        logger.error("❌ Erreur lors du débogage direct")
        sys.exit(1) 