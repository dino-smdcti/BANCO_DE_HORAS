// Central configuration / control center for client-side mask magic values.
const MASK_CONSTANTS = {
    // Maximum length (digits) for each masked field.
    CPF_MAX_LENGTH: 11,
    TIME_MAX_LENGTH: 6,
    REGISTRATION_MAX_LENGTH: 10,

    // Meta-flag used to mark inputs that already have an active mask.
    MASKED_FLAG: 'true',

    // Time input field names that receive the HH:MM[:SS] mask.
    TIME_FIELDS: [
        'arrival',
        'lunch_start',
        'lunch_end',
        'departure',
        'expected_arrival',
        'expected_lunch_start',
        'expected_lunch_end',
        'expected_departure'
    ]
};

document.addEventListener('DOMContentLoaded', function() {
    const applyMask = (input, maskFunc) => {
        input.addEventListener('input', (e) => {
            e.target.value = maskFunc(e.target.value);
        });
    };

    const cpfMask = (v) => {
        v = v.replace(/\D/g, ""); // Remove tudo o que não é dígito
        v = v.substring(0, MASK_CONSTANTS.CPF_MAX_LENGTH); // Limita a 11 caracteres
        v = v.replace(/(\d{3})(\d)/, "$1.$2"); // Coloca ponto entre o terceiro e o quarto dígitos
        v = v.replace(/(\d{3})(\d)/, "$1.$2"); // Coloca ponto entre o sexto e o sétimo dígitos
        v = v.replace(/(\d{3})(\d{1,2})$/, "$1-$2"); // Coloca hífen entre o nono e o décimo dígitos
        return v;
    };

    const timeMask = (v) => {
        v = v.replace(/\D/g, ""); // Remove tudo o que não é dígito
        v = v.substring(0, MASK_CONSTANTS.TIME_MAX_LENGTH); // Limita a 6 dígitos (HHMMSS)
        
        if (v.length > 4) {
            v = v.replace(/(\d{2})(\d{2})(\d{1,2})/, "$1:$2:$3");
        } else if (v.length > 2) {
            v = v.replace(/(\d{2})(\d{1,2})/, "$1:$2");
        }
        return v;
    };

    const registrationMask = (v) => {
        return v.replace(/\D/g, "").substring(0, MASK_CONSTANTS.REGISTRATION_MAX_LENGTH); // Apenas números, limite de 10
    };

    // Aplicar a campos específicos por seletor ou classe
    document.querySelectorAll('input[name="cpf"]').forEach(el => applyMask(el, cpfMask));
    document.querySelectorAll('input[name="registration_number"]').forEach(el => applyMask(el, registrationMask));
    
    // Campos de tempo
    const timeFields = MASK_CONSTANTS.TIME_FIELDS;
    timeFields.forEach(name => {
        document.querySelectorAll(`input[name="${name}"]`).forEach(el => applyMask(el, timeMask));
    });

    // Delegar para modais e elementos dinâmicos
    document.addEventListener('focusin', (e) => {
        if (e.target.tagName === 'INPUT') {
            const name = e.target.getAttribute('name');
            if (name === 'cpf' && !e.target.dataset.masked) {
                applyMask(e.target, cpfMask);
                e.target.dataset.masked = MASK_CONSTANTS.MASKED_FLAG;
            } else if (name === 'registration_number' && !e.target.dataset.masked) {
                applyMask(e.target, registrationMask);
                e.target.dataset.masked = MASK_CONSTANTS.MASKED_FLAG;
            } else if ((timeFields.some(f => name.startsWith(f)) || timeFields.includes(name)) && !e.target.dataset.masked) {
                applyMask(e.target, timeMask);
                e.target.dataset.masked = MASK_CONSTANTS.MASKED_FLAG;
            }
        }
    });
});
