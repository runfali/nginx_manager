/**
 * 动画效果交互逻辑
 */

document.addEventListener('DOMContentLoaded', function () {
    // 初始化所有卡片和表格的动画效果
    initAnimations();

    // 初始化表单验证动画
    initFormValidation();

    // 初始化操作结果提示动画
    initResultModal();
});

/**
 * 初始化页面基本动画效果
 */
function initAnimations() {
    // 为所有卡片添加淡入效果
    document.querySelectorAll('.card').forEach(card => {
        card.classList.add('fade-in');
    });

    // 为所有按钮添加点击动画效果
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('mousedown', function () {
            this.style.transform = 'scale(0.95)';
        });

        btn.addEventListener('mouseup', function () {
            this.style.transform = '';
        });

        btn.addEventListener('mouseleave', function () {
            this.style.transform = '';
        });
    });
}

/**
 * 初始化表单验证动画
 */
function initFormValidation() {
    // 为所有表单添加提交验证动画
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function (event) {
            let isValid = form.checkValidity();

            if (!isValid) {
                event.preventDefault();
                event.stopPropagation();

                // 查找第一个无效的输入框并添加错误动画
                const invalidInput = form.querySelector(':invalid');
                if (invalidInput) {
                    invalidInput.classList.add('error-animation');
                    setTimeout(() => {
                        invalidInput.classList.remove('error-animation');
                    }, 500);
                    invalidInput.focus();
                }
            } else {
                // 添加提交中的加载状态
                const submitBtn = form.querySelector('[type="submit"]');
                if (submitBtn && !submitBtn.querySelector('.loading')) {
                    const loadingSpinner = document.createElement('span');
                    loadingSpinner.className = 'loading';
                    submitBtn.prepend(loadingSpinner);
                    submitBtn.disabled = true;
                }
            }

            form.classList.add('was-validated');
        });

        // 为输入框添加实时验证反馈
        form.querySelectorAll('.form-control, .form-select').forEach(input => {
            input.addEventListener('input', function () {
                if (this.checkValidity()) {
                    this.classList.remove('error-animation');
                    if (this.value) {
                        this.classList.add('success-animation');
                        setTimeout(() => {
                            this.classList.remove('success-animation');
                        }, 500);
                    }
                }
            });
        });
    });
}

/**
 * 初始化操作结果提示模态框动画
 */
function initResultModal() {
    // 获取操作结果提示模态框
    const resultModal = document.getElementById('resultModal');
    if (!resultModal) return;

    // 监听模态框显示事件
    resultModal.addEventListener('show.bs.modal', function (event) {
        const resultMessage = document.getElementById('resultMessage');
        if (!resultMessage) return;

        // 根据消息内容添加不同的动画效果
        if (resultMessage.textContent.includes('成功') ||
            resultMessage.textContent.includes('已完成')) {
            resultMessage.classList.add('text-success');
            resultMessage.classList.add('success-animation');
        } else if (resultMessage.textContent.includes('错误') ||
            resultMessage.textContent.includes('失败')) {
            resultMessage.classList.add('text-danger');
            resultMessage.classList.add('error-animation');
        }
    });

    // 监听模态框隐藏事件，移除动画类
    resultModal.addEventListener('hidden.bs.modal', function (event) {
        const resultMessage = document.getElementById('resultMessage');
        if (!resultMessage) return;

        resultMessage.classList.remove('text-success', 'text-danger', 'success-animation', 'error-animation');
    });
}

/**
 * 显示操作结果提示
 * @param {string} message - 提示消息
 * @param {boolean} isSuccess - 是否成功
 */
function showResultMessage(message, isSuccess = true) {
    const resultModal = document.getElementById('resultModal');
    const resultMessage = document.getElementById('resultMessage');

    if (resultModal && resultMessage) {
        resultMessage.textContent = message;
        resultMessage.className = isSuccess ? 'text-success' : 'text-danger';
        resultMessage.classList.add(isSuccess ? 'success-animation' : 'error-animation');

        const modal = new bootstrap.Modal(resultModal);
        modal.show();
    }
}

/**
 * 添加加载动画到按钮
 * @param {HTMLElement} button - 按钮元素
 */
function addLoadingToButton(button) {
    if (!button.querySelector('.loading')) {
        const loadingSpinner = document.createElement('span');
        loadingSpinner.className = 'loading';
        button.prepend(loadingSpinner);
        button.disabled = true;
    }
}

/**
 * 移除按钮的加载动画
 * @param {HTMLElement} button - 按钮元素
 */
function removeLoadingFromButton(button) {
    const loadingSpinner = button.querySelector('.loading');
    if (loadingSpinner) {
        loadingSpinner.remove();
        button.disabled = false;
    }
}