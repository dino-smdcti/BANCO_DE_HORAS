document.addEventListener('DOMContentLoaded', () => {
    // Universal form submit handler
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.classList.contains('no-loading')) {
                setLoadingState(submitBtn);
            }
        });
    });

    // Universal link/button navigation handler
    document.querySelectorAll('a.btn, button.btn').forEach(el => {
        el.addEventListener('click', function(e) {
            // Exclude modal triggers, dropdowns, and buttons that aren't navigation/actions
            if (this.hasAttribute('data-bs-toggle') || this.getAttribute('type') === 'button' || this.classList.contains('no-loading')) {
                return;
            }
            setLoadingState(this);
        });
    });
});

function setLoadingState(element) {
    element.disabled = true;
    element.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Processando...`;
}

function markRead(url) {
    fetch(url, { method: 'POST' })
    .then(r => {
        if(r.ok) {
            const badge = document.getElementById('notifBadge');
            if(badge) badge.classList.add('d-none');
        }
    });
}

function showConfirmModal(modalId) {
    const modalElement = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalElement);
    const timeSpan = document.getElementById('confirmTime');
    const locSpan = document.getElementById('confirmLoc');
    const locationInput = document.getElementById('locationInput');
    const mapContainer = document.getElementById('mapContainer');
    const modalMap = document.getElementById('modalMap');
    const locStatus = document.getElementById('locStatus');
    const btnConfirm = document.getElementById('btnConfirmPonto');
    const clockForm = document.getElementById('clockForm');
    
    const now = new Date();
    timeSpan.innerText = now.toLocaleTimeString();
    
    // Reset state
    btnConfirm.disabled = true;
    btnConfirm.innerHTML = 'Confirmar e Registrar';
    mapContainer.classList.add('d-none');
    locStatus.classList.remove('d-none');
    locSpan.innerText = "Obtendo localização...";
    locSpan.className = "";
    modalMap.src = "";

    modal.show();

    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const locStr = `${lat},${lng}`;
                locationInput.value = locStr;
                
                modalMap.src = `https://www.google.com/maps?q=${locStr}&output=embed`;
                
                // Show map when iframe is loaded
                modalMap.onload = function() {
                    mapContainer.classList.remove('d-none');
                    locStatus.classList.add('d-none');
                    btnConfirm.disabled = false;
                };
            },
            (error) => {
                console.error("Geolocation error:", error);
                locStatus.querySelector('.spinner-border').classList.add('d-none');
                locSpan.innerText = "Erro ao obter localização. Por favor, permita o acesso à sua localização para registrar o ponto.";
                locSpan.classList.add("text-danger", "small", "d-block", "mt-2");
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    } else {
        locStatus.querySelector('.spinner-border').classList.add('d-none');
        locSpan.innerText = "Geolocalização não suportada pelo seu navegador.";
        locSpan.classList.add("text-danger");
    }

    // Handle form submission to prevent multiple clicks
    if (clockForm) {
        clockForm.onsubmit = function() {
            btnConfirm.disabled = true;
            btnConfirm.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Registrando...`;
            return true;
        };
    }
}
