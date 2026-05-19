document.addEventListener('DOMContentLoaded', () => {
    // Universal form submit handler
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            const submitBtn = this.querySelector('button[type="submit"], input[type="submit"]');
            if (submitBtn && !submitBtn.classList.contains('no-loading')) {
                setLoadingState(submitBtn);
            }
        });
    });

    // Universal link/button navigation handler
    document.querySelectorAll('a.btn, button.btn').forEach(el => {
        el.addEventListener('click', function(e) {
            // Exclude modal triggers, dropdowns, and buttons that aren't navigation/actions
            if (this.hasAttribute('data-bs-toggle') || 
                this.getAttribute('data-bs-target') || 
                this.getAttribute('type') === 'button' || 
                this.classList.contains('no-loading')) {
                return;
            }
            setLoadingState(this);
        });
    });
});

function setLoadingState(element) {
    const loadingHtml = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Processando...`;
    
    if (element.tagName.toLowerCase() === 'input') {
        element.value = "Processando...";
    } else {
        element.innerHTML = loadingHtml;
    }

    // Delay disabling slightly to ensure name/value is sent in POST request
    setTimeout(() => {
        element.disabled = true;
    }, 10);
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

function showConfirmModal(modalId, nextStage, scheduledTime) {
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
    
    // Add dynamic input for time if we want to allow editing, 
    // for now just display current time as default/placeholder
    const now = new Date();
    const formattedTime = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    timeSpan.innerHTML = `
        <div class="input-group">
            <span class="input-group-text bg-light text-muted">Sugestão: ${scheduledTime || '--:--'}</span>
            <input type="text" class="form-control" value="${formattedTime}" disabled>
        </div>
    `;
    
    // Reset state
    btnConfirm.disabled = true;
    btnConfirm.innerHTML = 'Confirmar e Registrar';
    mapContainer.classList.add('d-none');
    locStatus.classList.remove('d-none');
    locSpan.innerText = "Obtendo localização...";
    locSpan.className = "";
    modalMap.src = "";

    modal.show();
    // ... rest of geolocation code ...
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                const locStr = `${lat},${lng}`;
                locationInput.value = locStr;
                
                modalMap.src = `https://www.google.com/maps?q=${locStr}&output=embed`;
                
                mapContainer.classList.remove('d-none');
                locStatus.classList.add('d-none');
                btnConfirm.disabled = false;
            },
            (error) => {
                console.error("Geolocation error:", error);
                locStatus.querySelector('.spinner-border').classList.add('d-none');
                locSpan.innerText = "Localização não obtida. Você ainda pode registrar seu ponto.";
                locSpan.classList.add("text-muted", "small", "d-block", "mt-2");
                btnConfirm.disabled = false;
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    } else {
        locStatus.querySelector('.spinner-border').classList.add('d-none');
        locSpan.innerText = "Geolocalização não suportada pelo seu navegador.";
        locSpan.classList.add("text-danger");
    }

    if (clockForm) {
        clockForm.onsubmit = function() {
            btnConfirm.disabled = true;
            btnConfirm.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Registrando...`;
            return true;
        };
    }
}

function updateDynamicTimer() {
    const timerElement = document.getElementById('dynamic-saldo-dia');
    const totalWorkedElement = document.getElementById('dynamic-worked-total');
    if (!timerElement || !totalWorkedElement) return;

    const arrivalStr = timerElement.getAttribute('data-arrival');
    const lunchStartStr = timerElement.getAttribute('data-lunch-start');
    const lunchEndStr = timerElement.getAttribute('data-lunch-end');
    const departureStr = timerElement.getAttribute('data-departure');
    const expectedDailyMinutes = parseInt(timerElement.getAttribute('data-expected-daily') || '0');
    const hasLunchBreak = timerElement.getAttribute('data-has-lunch-break') === 'true';

    function parseTime(timeStr) {
        if (!timeStr || timeStr.trim() === '') return null;
        const parts = timeStr.split(':').map(Number);
        if (parts.some(isNaN)) return null;
        const d = new Date();
        d.setHours(parts[0] || 0, parts[1] || 0, parts[2] || 0, 0);
        return d;
    }

    const arrival = parseTime(arrivalStr);
    const lunchStart = parseTime(lunchStartStr);
    const lunchEnd = parseTime(lunchEndStr);
    const departure = parseTime(departureStr);
    const now = new Date();

    let workedSeconds = 0;

    if (arrival) {
        if (hasLunchBreak) {
            // Morning block
            if (lunchStart) {
                workedSeconds += Math.max(0, (lunchStart - arrival) / 1000);
            } else if (!departure) {
                workedSeconds += Math.max(0, (now - arrival) / 1000);
            }

            // Afternoon block
            if (lunchEnd) {
                const endAfternoon = departure || now;
                workedSeconds += Math.max(0, (endAfternoon - lunchEnd) / 1000);
            }
        } else {
            // Continuous block
            const endDay = departure || now;
            workedSeconds += Math.max(0, (endDay - arrival) / 1000);
        }
    }

    const workedMinutes = workedSeconds / 60;
    const saldoMinutes = workedMinutes - expectedDailyMinutes;

    // Update total worked display
    const h = Math.floor(workedSeconds / 3600);
    const m = Math.floor((workedSeconds % 3600) / 60);
    totalWorkedElement.innerText = `(${h}h ${m}m)`;

    // Update balance display
    const absSaldo = Math.abs(saldoMinutes);
    const sh = Math.floor(absSaldo / 60);
    const sm = Math.floor(absSaldo % 60);
    const ss = Math.floor((absSaldo * 60) % 60);
    
    timerElement.innerText = `${saldoMinutes >= 0 ? '+' : '-'}${sh}h ${sm}m ${ss}s`;
    timerElement.className = `fw-bold ${saldoMinutes >= 0 ? 'text-success' : 'text-danger'}`;
}

// Start timer if elements exist
function initDynamicTimer() {
    console.log("Checking for dynamic timer elements...");
    const timerElement = document.getElementById('dynamic-saldo-dia');
    if (timerElement) {
        console.log("Timer element found, starting interval.");
        setInterval(updateDynamicTimer, 1000);
        updateDynamicTimer();
    } else {
        console.log("Timer element not found on this page.");
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDynamicTimer);
} else {
    initDynamicTimer();
}
