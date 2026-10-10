cmake_minimum_required(VERSION 3.24)
project(MeowneroWallet VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core Gui Qml Quick QuickControls2 Test)
qt_standard_project_setup(REQUIRES 6.12)

# Shared controller: exact amounts, ledger, session-bound actions and the
# simulated backend. QML only sees what WalletController exposes.
qt_add_library(wallet_core STATIC
    src/amount.cpp src/amount.h
    src/ledger.cpp src/ledger.h
    src/simulatedbackend.cpp src/simulatedbackend.h
    src/walletcontroller.cpp src/walletcontroller.h
    src/activitymodel.cpp src/activitymodel.h
)
target_include_directories(wallet_core PUBLIC src)
target_link_libraries(wallet_core PUBLIC Qt6::Core Qt6::Gui Qt6::Qml)
target_compile_options(wallet_core PRIVATE -Wall -Wextra -Werror=return-type)

qt_add_executable(meownero-wallet src/main.cpp)
set_source_files_properties(qml/Theme.qml qml/UiState.qml PROPERTIES QT_QML_SINGLETON_TYPE TRUE)
qt_add_qml_module(meownero-wallet
    URI Meownero
    VERSION 1.0
    QML_FILES
        qml/Main.qml
        qml/Theme.qml
        qml/AppButton.qml
        qml/AmountLabel.qml
        qml/NetTag.qml
        qml/Banner.qml
        qml/ConditionBanners.qml
        qml/AddressText.qml
        qml/FieldError.qml
        qml/PageHeading.qml
        qml/ShellPage.qml
        qml/Sidebar.qml
        qml/CoinMark.qml
        qml/AppDialog.qml
        qml/OverviewPage.qml
        qml/ActivityPage.qml
        qml/SendPage.qml
        qml/ReceivePage.qml
        qml/NodePage.qml
        qml/WalletPage.qml
        qml/OnboardingPage.qml
        qml/WordsGrid.qml
        qml/Icon.qml
        qml/Spinner.qml
        qml/ActivityList.qml
        qml/ChoiceItem.qml
        qml/DefRow.qml
        qml/SectionLabel.qml
        qml/DetailDialog.qml
        qml/Field.qml
        qml/UiState.qml
        qml/PageBase.qml
        qml/ReviewerFixtures.qml
)
target_link_libraries(meownero-wallet PRIVATE wallet_core Qt6::Quick Qt6::QuickControls2)

enable_testing()
foreach(t tst_amount tst_controller)
    qt_add_executable(${t} tests/${t}.cpp)
    target_link_libraries(${t} PRIVATE wallet_core Qt6::Test)
    add_test(NAME ${t} COMMAND ${t})
    set_tests_properties(${t} PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")
endforeach()
