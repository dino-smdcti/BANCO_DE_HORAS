// Central configuration / control center for client-side magic values.
const APP_CONSTANTS = {
    // Time conversions.
    MS_PER_SECOND: 1000,
    SECONDS_PER_MINUTE: 60,
    SECONDS_PER_HOUR: 3600,

    // Clock-ins closer than this many minutes apart are flagged as duplicates.
    DUPLICATE_THRESHOLD_MINUTES: 15,

    // Delay (ms) before disabling a submit button so the POST payload is sent.
    SUBMIT_DISABLE_DELAY_MS: 10,

    // Geolocation acquisition timeout (ms).
    GEOLOCATION_TIMEOUT_MS: 10000,

    // Loading label shown on buttons/inputs while a request is in flight.
    LOADING_LABEL: 'Processando...',

    // Management roles that always see every clock stage.
    MANAGEMENT_ROLES: ['manager', 'admin'],

    // Maps backend stage labels to form stage values.
    STAGE_LABEL_TO_VALUE: {
        'Chegada': 'arrival',
        'Saída Almoço': 'lunch_start',
        'Retorno Almoço': 'lunch_end',
        'Fim Jornada': 'departure'
    },

    // Google Maps embed URL template used to render the clock location.
    MAP_EMBED_URL: 'https://www.google.com/maps?q=${loc}&output=embed'
};

// Reads the CSRF token emitted by the server's meta tag so fetch() POSTs can
// include the X-CSRFToken header required by Flask-WTF's CSRFProtect.
function getCsrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

// Adds the CSRF header to any fetch() request when a token is available.
function csrfFetch(url, options) {
    const opts = options || {};
    const token = getCsrfToken();
    if (token && opts.method && opts.method.toUpperCase() !== 'GET') {
        opts.headers = Object.assign({}, opts.headers, { 'X-CSRFToken': token });
    }
    return fetch(url, opts);
}

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
    const loadingHtml = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> ${APP_CONSTANTS.LOADING_LABEL}`;
    
    if (element.tagName.toLowerCase() === 'input') {
        element.value = APP_CONSTANTS.LOADING_LABEL;
    } else {
        element.innerHTML = loadingHtml;
    }

    // Delay disabling slightly to ensure name/value is sent in POST request
    setTimeout(() => {
        element.disabled = true;
    }, APP_CONSTANTS.SUBMIT_DISABLE_DELAY_MS);
}

function markRead(url) {
    csrfFetch(url, { method: 'POST' })
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

    // Duplicate Check threshold
    let isTooClose = false;
    if (lastClockTime) {
        const [lh, lm, ls] = lastClockTime.split(':').map(Number);
        const lastDate = new Date();
        lastDate.setHours(lh, lm, ls, 0);
        
        const diffMs = Math.abs(now - lastDate);
        const diffMins = diffMs / (APP_CONSTANTS.MS_PER_SECOND * APP_CONSTANTS.SECONDS_PER_MINUTE);
        
        if (diffMins < APP_CONSTANTS.DUPLICATE_THRESHOLD_MINUTES) {
            isTooClose = true;
            duplicateWarning.classList.remove('d-none');
        }
    }

    // Map nextStage label (from backend) to value
    const stageMap = APP_CONSTANTS.STAGE_LABEL_TO_VALUE;
    
    let currentSelectedStage = stageMap[nextStage] || 'arrival';

    // Handle lunch break visibility (Managers/Admins always see all buttons)
    const lunchStartRadio = document.getElementById('stage_lunch_start');
    const lunchEndRadio = document.getElementById('stage_lunch_end');
    const lunchStartLabel = document.querySelector('label[for="stage_lunch_start"]');
    const lunchEndLabel = document.querySelector('label[for="stage_lunch_end"]');

    const isManagement = APP_CONSTANTS.MANAGEMENT_ROLES.includes(userRole);

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
                modalMap.src = APP_CONSTANTS.MAP_EMBED_URL.replace('${loc}', locStr);
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
            { enableHighAccuracy: true, timeout: APP_CONSTANTS.GEOLOCATION_TIMEOUT_MS }
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
                workedSeconds += Math.max(0, (lunchStart - arrival) / APP_CONSTANTS.MS_PER_SECOND);
            } else if (!departure) {
                workedSeconds += Math.max(0, (now - arrival) / APP_CONSTANTS.MS_PER_SECOND);
            }

            // Afternoon block
            if (lunchEnd) {
                const endAfternoon = departure || now;
                workedSeconds += Math.max(0, (endAfternoon - lunchEnd) / APP_CONSTANTS.MS_PER_SECOND);
            }
        } else {
            // Continuous block
            const endDay = departure || now;
            workedSeconds += Math.max(0, (endDay - arrival) / APP_CONSTANTS.MS_PER_SECOND);
        }
    }

    const workedMinutes = workedSeconds / APP_CONSTANTS.SECONDS_PER_MINUTE;
    const saldoMinutes = workedMinutes - expectedDailyMinutes;

    // Update total worked display
    const h = Math.floor(workedSeconds / APP_CONSTANTS.SECONDS_PER_HOUR);
    const m = Math.floor((workedSeconds % APP_CONSTANTS.SECONDS_PER_HOUR) / APP_CONSTANTS.SECONDS_PER_MINUTE);
    totalWorkedElement.innerText = `(${h}h ${m}m)`;

    // Update balance display
    const absSaldo = Math.abs(saldoMinutes);
    const sh = Math.floor(absSaldo / APP_CONSTANTS.SECONDS_PER_MINUTE);
    const sm = Math.floor(absSaldo % APP_CONSTANTS.SECONDS_PER_MINUTE);
    const ss = Math.floor((absSaldo * APP_CONSTANTS.SECONDS_PER_MINUTE) % APP_CONSTANTS.SECONDS_PER_MINUTE);
    
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
