document.addEventListener('DOMContentLoaded', function() {
    const applyMask = (input, maskFunc) => {
        input.addEventListener('input', (e) => {
            e.target.value = maskFunc(e.target.value);
        });
    };

    const cpfMask = (v) => {
        v = v.replace(/\D/g, ""); // Remove tudo o que não é dígito
        v = v.substring(0, 11); // Limita a 11 caracteres
        v = v.replace(/(\d{3})(\d)/, "$1.$2"); // Coloca ponto entre o terceiro e o quarto dígitos
        v = v.replace(/(\d{3})(\d)/, "$1.$2"); // Coloca ponto entre o sexto e o sétimo dígitos
        v = v.replace(/(\d{3})(\d{1,2})$/, "$1-$2"); // Coloca hífen entre o nono e o décimo dígitos
        return v;
    };

    const timeMask = (v) => {
        v = v.replace(/\D/g, ""); // Remove tudo o que não é dígito
        v = v.substring(0, 4); // Limita a 4 dígitos
        if (v.length > 2) {
            v = v.replace(/(\d{2})(\d{1,2})/, "$1:$2");
        }
        return v;
    };

    const registrationMask = (v) => {
        return v.replace(/\D/g, "").substring(0, 10); // Apenas números, limite de 10
    };

    // Aplicar a campos específicos por seletor ou classe
    document.querySelectorAll('input[name="cpf"]').forEach(el => applyMask(el, cpfMask));
    document.querySelectorAll('input[name="registration_number"]').forEach(el => applyMask(el, registrationMask));
    
    // Campos de tempo
    const timeFields = ['arrival', 'lunch_start', 'lunch_end', 'departure', 'expected_arrival', 'expected_lunch_start', 'expected_lunch_end', 'expected_departure'];
    timeFields.forEach(name => {
        document.querySelectorAll(`input[name="${name}"]`).forEach(el => applyMask(el, timeMask));
    });

    // Delegar para modais e elementos dinâmicos
    document.addEventListener('focusin', (e) => {
        if (e.target.tagName === 'INPUT') {
            const name = e.target.getAttribute('name');
            if (name === 'cpf' && !e.target.dataset.masked) {
                applyMask(e.target, cpfMask);
                e.target.dataset.masked = "true";
            } else if (name === 'registration_number' && !e.target.dataset.masked) {
                applyMask(e.target, registrationMask);
                e.target.dataset.masked = "true";
            } else if (timeFields.includes(name) && !e.target.dataset.masked) {
                applyMask(e.target, timeMask);
                e.target.dataset.masked = "true";
            }
        }
    });
});
