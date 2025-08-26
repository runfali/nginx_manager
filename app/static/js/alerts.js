// 引入SweetAlert2库
document.addEventListener('DOMContentLoaded', function () {
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/sweetalert2@11';
    document.head.appendChild(script);
});

// 统一的弹窗管理函数
const showAlert = {
    // 成功提示
    success: function (title, text = '') {
        return Swal.fire({
            title: title,
            text: text,
            icon: 'success',
            confirmButtonText: '确定',
            confirmButtonColor: '#28a745'
        });
    },

    // 错误提示
    error: function (title, text = '') {
        return Swal.fire({
            title: title,
            text: text,
            icon: 'error',
            confirmButtonText: '确定',
            confirmButtonColor: '#dc3545'
        });
    },

    // 确认对话框
    confirm: function (title, text = '') {
        return Swal.fire({
            title: title,
            text: text,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#6c757d'
        });
    },

    // 加载中提示
    loading: function (title = '处理中...') {
        Swal.fire({
            title: title,
            allowOutsideClick: false,
            showConfirmButton: false,
            willOpen: () => {
                Swal.showLoading();
            }
        });
    },

    // 关闭加载中提示
    closeLoading: function () {
        Swal.close();
    },

    // 同步配置提示
    syncConfig: {
        start: function () {
            showAlert.loading('正在同步配置...');
        },
        success: function () {
            showAlert.success('同步成功', '配置已成功同步到服务器');
        },
        error: function (message) {
            showAlert.error('同步失败', message || '请检查网络连接或联系管理员');
        }
    },

    // 测试配置提示
    testConfig: {
        start: function () {
            showAlert.loading('正在测试配置...');
        },
        success: function () {
            showAlert.success('测试成功', '配置语法检查通过');
        },
        error: function (message) {
            showAlert.error('测试失败', message || '配置语法检查未通过');
        }
    },

    // 重载配置提示
    reloadConfig: {
        start: function () {
            showAlert.loading('正在重载配置...');
        },
        success: function () {
            showAlert.success('重载成功', 'Nginx配置已成功重载');
        },
        error: function (message) {
            showAlert.error('重载失败', message || '请检查配置或联系管理员');
        }
    }
};