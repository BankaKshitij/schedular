## 🗓️ Calendly Clone:
A simple and flexible meeting scheduler inspired by Calendly. This project demonstrates my implementation for Harbor, focusing on meeting scheduling, availability management, meeting extensions, and rescheduling.

## 📎 Links
### GitHub Repo: Schedular(https://github.com/BankaKshitij/schedular)
### TRD & PRD & Future Enhancements: Notion Document(https://tar-verbena-7a7.notion.site/Calendly-Clone-134afdd29b0f80848196f49ef3665dd5)
### Postman Collection for Testing: Attached in the provided email.

## 📋 Assumptions
Users: The system includes two types of users - Organizers and Attendees. Only authenticated users are allowed to schedule meetings.
Availability: Only Organizers can set availability, and attendees can book meetings within these availability slots.
Meeting Types: Meetings are categorized, including options like focus time, product discussions, etc. Focus times are unavailable for regular meetings.
Conflicting Meetings: Meetings can only be extended if there are no conflicts with the organizer's and attendees' existing schedules.

## 🚀 Installation Guide

`pip install -r requirements.txt`

Prerequisites
Python 3.8+
Django 4.0+
pip for package installation
PostgreSQL or SQLite for local database setup


## ✨ Features

### 📅 Current Features

#### Meeting Scheduling: Schedule meetings based on an organizer's availability.
#### Meeting Extensions: Allow the organizer to extend meetings if no conflicts exist.
#### Bulk Rescheduling Suggestions: Uses the OpenAI API to provide possible reschedule slots based on everyone's availability.
#### Swagger API Documentation: Available at /api-docs/.

### 🔮 Upcoming Features
#### Bulk Meeting Rescheduling: Reschedule all meetings for a given date.
#### Reviews for Meetings: Collect feedback after meetings to inform HR teams.
#### AI-Driven Rescheduling: Personalized suggestions for rescheduling using behavioral data insights.

### 💡 Product Muscle
#### Flexibility: Users can extend or reschedule meetings easily.
#### User Experience: Built-in checks for scheduling conflicts and intelligent rescheduling suggestions using GPT.
#### GPT Integration: Use of GPT ensures smart, user-centric scheduling suggestions that accommodate everyone's availability.

### 📈 Future Enhancements
#### Bulk Meeting Rescheduling for Specific Dates: Allow users to reschedule all meetings set for a particular day.
#### AI-Driven Personalized Rescheduling: Provide more tailored suggestions using historical data and behavior patterns.
#### Meeting Reviews and HR Insights: Collect participant feedback to understand issues and improve productivity.
#### Scheduling Analytics: Build analytics to improve scheduling efficiency over time.

### 🔍 Testing
#### A Postman Collection is provided, allowing you to interact with the API and explore different features such as:

1. User Authentication: User sign-up and log-in endpoints.
2. Availability Management: Set up availability slots.
3. Meeting Scheduling: Schedule new meetings based on availability.
4. Meeting Extension and Rescheduling: Extend and reschedule meetings as needed.
