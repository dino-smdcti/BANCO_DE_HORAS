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

function showConfirmModal(modalId, nextStage, scheduledTime, hasLunchBreak, lastClockTime, userRole) {
    const modalElement = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalElement);
    const timeSpan = document.getElementById('confirmTime');
    const locSpan = document.getElementById('confirmLoc');
    const locationInput = document.getElementById('locationInput');
    const mapSection = document.getElementById('mapSection');
    const modalMap = document.getElementById('modalMap');
    const locStatus = document.getElementById('locStatus');
    const btnConfirm = document.getElementById('btnConfirmPonto');
    const clockForm = document.getElementById('clockForm');
    
    // Smart Detection Elements
    const smartAlert = document.getElementById('smartStageAlert');
    const suggestedLabel = document.getElementById('suggestedStageLabel');
    const stageInput = document.getElementById('stageInput');
    const pontoBtn = document.getElementById('pontoBtn');

    // Duplicate Detection Elements
    const duplicateWarning = document.getElementById('duplicateWarning');
    const confirmDuplicate = document.getElementById('confirmDuplicate');

    // Reset UI
    smartAlert.classList.add('d-none');
    duplicateWarning.classList.add('d-none');
    confirmDuplicate.checked = false;
    
    const now = new Date();
    timeSpan.innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

    // 15-minute Duplicate Check
    let isTooClose = false;
    if (lastClockTime) {
        const [lh, lm, ls] = lastClockTime.split(':').map(Number);
        const lastDate = new Date();
        lastDate.setHours(lh, lm, ls, 0);
        
        const diffMs = Math.abs(now - lastDate);
        const diffMins = diffMs / (1000 * 60);
        
        if (diffMins < 15) {
            isTooClose = true;
            duplicateWarning.classList.remove('d-none');
        }
    }

    // Map nextStage label (from backend) to value
    const stageMap = {
        'Chegada': 'arrival',
        'Saída Almoço': 'lunch_start',
        'Retorno Almoço': 'lunch_end',
        'Fim Jornada': 'departure'
    };
    
    let currentSelectedStage = stageMap[nextStage] || 'arrival';

    // Handle lunch break visibility (Managers/Admins always see all buttons)
    const lunchStartRadio = document.getElementById('stage_lunch_start');
    const lunchEndRadio = document.getElementById('stage_lunch_end');
    const lunchStartLabel = document.querySelector('label[for="stage_lunch_start"]');
    const lunchEndLabel = document.querySelector('label[for="stage_lunch_end"]');

    const isManagement = (userRole === 'manager' || userRole === 'admin');

    if (hasLunchBreak === false && !isManagement) {
        if (lunchStartRadio) lunchStartRadio.classList.add('d-none');
        if (lunchEndRadio) lunchEndRadio.classList.add('d-none');
        if (lunchStartLabel) lunchStartLabel.classList.add('d-none');
        if (lunchEndLabel) lunchEndLabel.classList.add('d-none');
    } else {
        if (lunchStartRadio) lunchStartRadio.classList.remove('d-none');
        if (lunchEndRadio) lunchEndRadio.classList.remove('d-none');
        if (lunchStartLabel) lunchStartLabel.classList.remove('d-none');
        if (lunchEndLabel) lunchEndLabel.classList.remove('d-none');
    }

    // Initialize Radio Buttons
    const radios = document.querySelectorAll('input[name="stage_radio"]');
    radios.forEach(r => {
        if (r.value === currentSelectedStage) {
            r.checked = true;
            stageInput.value = r.value;
        }
        r.onchange = function() {
            stageInput.value = this.value;
        };
    });
    
    // Function to check if confirm should be enabled
    function updateConfirmState(locationObtained) {
        const needsDupConfirm = isTooClose && !confirmDuplicate.checked;
        btnConfirm.disabled = !locationObtained || needsDupConfirm;
    }

    confirmDuplicate.onchange = () => {
        const hasLoc = !!locationInput.value;
        updateConfirmState(hasLoc);
    };

    // Reset state
    btnConfirm.disabled = true;
    btnConfirm.innerHTML = 'Confirmar e Registrar';
    mapSection.classList.add('d-none');
    locStatus.classList.remove('d-none');
    locSpan.innerText = "Obtendo localização...";
    locSpan.className = "small ms-1";
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
                mapSection.classList.remove('d-none');
                locStatus.classList.add('d-none');
                
                updateConfirmState(true);
            },
            (error) => {
                console.error("Geolocation error:", error);
                const spinner = locStatus.querySelector('.spinner-border');
                if (spinner) spinner.classList.add('d-none');
                locSpan.innerText = "Localização não obtida. Você ainda pode registrar seu ponto.";
                
                updateConfirmState(true);
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    } else {
        const spinner = locStatus.querySelector('.spinner-border');
        if (spinner) spinner.classList.add('d-none');
        locSpan.innerText = "Geolocalização não suportada.";
        updateConfirmState(true);
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
